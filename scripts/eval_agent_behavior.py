import json
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.llm import BaseLLMClient
from app.data.seed import NPCS
from app.repositories.player_state_repository import PlayerStateRepository
from app.schemas.chat import AgentAction
from app.schemas.game import PlayerState
from app.schemas.llm import LLMChatResult
from app.services.chat_service import ChatService
from app.services.context_builder_service import ContextBuilderService
from app.services.game_service import GameService
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_service import MemoryService
from app.services.rag_knowledge_service import RagKnowledgeService
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.token_budget_service import TokenBudgetService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


DEFAULT_CASES_PATH = REPO_ROOT / "eval" / "agent_cases.jsonl"
DEFAULT_JSON_REPORT_PATH = REPO_ROOT / "eval" / "eval_report.json"
DEFAULT_MD_REPORT_PATH = REPO_ROOT / "eval" / "eval_report.md"
TMP_ROOT = REPO_ROOT / "eval" / ".tmp"


@dataclass
class EvalCase:
    case_id: str
    player_id: str
    npc_id: str
    message: str
    expected_tools: list[str] = field(default_factory=list)
    expected_knowledge_hit: bool | None = None
    expected_quest_state: dict[str, list[str]] = field(default_factory=dict)
    expected_reply_contains: list[str] = field(default_factory=list)
    rag_documents: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalEnvironment:
    chat_service: ChatService
    game_service: GameService
    trace_service: TraceService
    rag_service: RagKnowledgeService
    cleanup_paths: list[Path]

    def close(self) -> None:
        for resource in (
            self.chat_service,
            self.game_service,
            self.trace_service,
            self.rag_service,
        ):
            close = getattr(resource, "close", None)
            if close is not None:
                close()

        for path in self.cleanup_paths:
            _remove_path_best_effort(path)


class DeterministicEvalLLM(BaseLLMClient):
    """Offline deterministic LLM used only by the eval script."""

    def generate(self, prompt: str) -> LLMChatResult:
        lower_prompt = prompt.lower()

        if "i will help you find silver ore" in lower_prompt:
            return LLMChatResult(
                reply="Bring me silver ore and I will repair the old sword.",
                actions=[
                    AgentAction(
                        tool="create_quest",
                        args={"quest_id": "find_silver_ore"},
                    ),
                    AgentAction(
                        tool="update_relationship",
                        args={"npc_id": "blacksmith_001", "delta": 5},
                    ),
                ],
            )

        if "moonwell" in lower_prompt and "silver bell" in lower_prompt:
            return LLMChatResult(
                reply="The moonwell opens only when the silver bell rings.",
                actions=[],
            )

        if "village gate" in lower_prompt:
            return LLMChatResult(
                reply="The village gate is quiet, but the guard is watching the road.",
                actions=[],
            )

        return LLMChatResult(
            reply="I do not have anything useful to add right now.",
            actions=[],
        )


class EmptySharedKnowledgeService:
    def get_relevant_events(self, **kwargs) -> list:
        return []

    def close(self) -> None:
        pass


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            cases.append(EvalCase(**payload))
    return cases


def run_eval(
    cases_path: Path = DEFAULT_CASES_PATH,
    json_report_path: Path = DEFAULT_JSON_REPORT_PATH,
    md_report_path: Path = DEFAULT_MD_REPORT_PATH,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    case_results = [run_case(case) for case in cases]
    report = build_report(case_results)

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_report_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def run_case(case: EvalCase) -> dict[str, Any]:
    env = build_environment(case)
    started_at = time.perf_counter()
    error: str | None = None

    try:
        npc = next(npc for npc in NPCS if npc.npc_id == case.npc_id)
        response = env.chat_service.chat(
            npc=npc,
            player_state=env.game_service.get_player_state(case.player_id),
            message=case.message,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        player_state = env.game_service.get_player_state(case.player_id)
        trace = env.trace_service.latest_trace()

        actual_tools = [action.tool for action in response.actions]
        executed_tools = [
            result.tool
            for result in response.executed_actions
            if result.success
        ]
        rag_hit = bool(
            response.context_report
            and response.context_report.selected_rag_chunks > 0
        )
        quest_state_passed = check_quest_state(player_state, case.expected_quest_state)
        reply_passed = all(
            expected.lower() in response.reply.lower()
            for expected in case.expected_reply_contains
        )
        tools_passed = actual_tools == case.expected_tools
        rag_passed = (
            True
            if case.expected_knowledge_hit is None
            else rag_hit == case.expected_knowledge_hit
        )

        failures = []
        if not tools_passed:
            failures.append("tools")
        if not rag_passed:
            failures.append("rag_hit")
        if not quest_state_passed:
            failures.append("quest_state")
        if not reply_passed:
            failures.append("reply")

        return {
            "case_id": case.case_id,
            "passed": not failures,
            "failures": failures,
            "latency_ms": elapsed_ms,
            "expected_tools": case.expected_tools,
            "actual_tools": actual_tools,
            "executed_tools": executed_tools,
            "expected_knowledge_hit": case.expected_knowledge_hit,
            "rag_hit": rag_hit,
            "citations": [citation.model_dump(mode="json") for citation in response.citations],
            "expected_quest_state": case.expected_quest_state,
            "actual_quest_state": summarize_quest_state(player_state),
            "reply": response.reply,
            "token_estimate": (
                response.context_report.estimated_prompt_tokens
                if response.context_report
                else 0
            ),
            "trace_id": trace.request_id if trace else None,
            "error": error,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        error = str(exc)
        return {
            "case_id": case.case_id,
            "passed": False,
            "failures": ["exception"],
            "latency_ms": elapsed_ms,
            "expected_tools": case.expected_tools,
            "actual_tools": [],
            "executed_tools": [],
            "expected_knowledge_hit": case.expected_knowledge_hit,
            "rag_hit": False,
            "citations": [],
            "expected_quest_state": case.expected_quest_state,
            "actual_quest_state": {},
            "reply": "",
            "token_estimate": 0,
            "trace_id": None,
            "error": error,
        }
    finally:
        env.close()


def build_environment(case: EvalCase) -> EvalEnvironment:
    run_id = uuid.uuid4().hex
    run_dir = TMP_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    player_db_path = run_dir / "player_state.db"
    trace_db_path = run_dir / "traces.db"
    chroma_dir = run_dir / "chroma"

    token_budget_service = TokenBudgetService()
    game_service = GameService(PlayerStateRepository(db_path=str(player_db_path)))
    memory_service = MemoryService(max_messages=10)
    long_term_memory_service = EmptyLongTermMemoryService()
    shared_knowledge_service = EmptySharedKnowledgeService()
    rag_service = RagKnowledgeService(
        persist_dir=str(chroma_dir),
        collection_name=f"eval_rag_{run_id}",
        embedding_model_name="eval-missing-local-model",
        token_budget_service=token_budget_service,
        chunk_token_budget=120,
    )
    rag_service.embedding_model_unavailable = True
    for document in case.rag_documents:
        rag_service.import_document(**document)

    trace_service = TraceService(db_path=str(trace_db_path), max_records=50)
    chat_service = ChatService.__new__(ChatService)
    chat_service.llm_client = DeterministicEvalLLM()
    chat_service.memory_service = memory_service
    chat_service.long_term_memory_service = long_term_memory_service
    chat_service.shared_knowledge_service = shared_knowledge_service
    chat_service.tool_service = ToolService(
        game_service=game_service,
        shared_knowledge_service=shared_knowledge_service,
    )
    chat_service.reflection_service = None
    chat_service.reflection_worker = None
    chat_service.rag_knowledge_service = rag_service
    chat_service.context_builder_service = ContextBuilderService(token_budget_service)
    chat_service.trace_service = trace_service

    return EvalEnvironment(
        chat_service=chat_service,
        game_service=game_service,
        trace_service=trace_service,
        rag_service=rag_service,
        cleanup_paths=[run_dir],
    )


class EmptyLongTermMemoryService:
    def search_memory(self, **kwargs) -> list:
        return []

    def close(self) -> None:
        pass


def check_quest_state(
    player_state: PlayerState | None,
    expected: dict[str, list[str]],
) -> bool:
    if player_state is None:
        return False

    expected_active = set(expected.get("active", []))
    expected_completed = set(expected.get("completed", []))
    return expected_active.issubset(set(player_state.active_quests)) and (
        expected_completed.issubset(set(player_state.completed_quests))
    )


def summarize_quest_state(player_state: PlayerState | None) -> dict[str, list[str]]:
    if player_state is None:
        return {"active": [], "completed": []}
    return {
        "active": sorted(player_state.active_quests),
        "completed": sorted(player_state.completed_quests),
    }


def build_report(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(case_results)
    passed_cases = sum(1 for result in case_results if result["passed"])
    latencies = [result["latency_ms"] for result in case_results]
    token_estimates = [result["token_estimate"] for result in case_results]

    tool_cases = [result for result in case_results if result["expected_tools"] is not None]
    rag_cases = [
        result
        for result in case_results
        if result["expected_knowledge_hit"] is True
    ]
    quest_cases = [
        result
        for result in case_results
        if result["expected_quest_state"]
    ]

    metrics = {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "pass_rate": _safe_ratio(passed_cases, total_cases),
        "error_rate": _safe_ratio(
            sum(1 for result in case_results if result["error"]),
            total_cases,
        ),
        "tool_call_accuracy": _safe_ratio(
            sum(
                1
                for result in tool_cases
                if result["actual_tools"] == result["expected_tools"]
            ),
            len(tool_cases),
        ),
        "rag_hit_rate": _safe_ratio(
            sum(1 for result in rag_cases if result["rag_hit"]),
            len(rag_cases),
        ),
        "quest_success_rate": _safe_ratio(
            sum(
                1
                for result in quest_cases
                if "quest_state" not in result["failures"]
            ),
            len(quest_cases),
        ),
        "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 95),
        "avg_prompt_tokens": round(mean(token_estimates), 2) if token_estimates else 0.0,
        "total_prompt_tokens": sum(token_estimates),
    }

    return {
        "passed": passed_cases == total_cases,
        "metrics": metrics,
        "cases": case_results,
        "failed_cases": [
            result
            for result in case_results
            if not result["passed"]
        ],
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Agent/RAG Eval Report",
        "",
        f"Passed: `{report['passed']}`",
        "",
        "## Metrics",
        "",
        f"- Total cases: {metrics['total_cases']}",
        f"- Passed cases: {metrics['passed_cases']}",
        f"- Pass rate: {metrics['pass_rate']:.2%}",
        f"- RAG hit rate: {metrics['rag_hit_rate']:.2%}",
        f"- Tool call accuracy: {metrics['tool_call_accuracy']:.2%}",
        f"- Quest success rate: {metrics['quest_success_rate']:.2%}",
        f"- Error rate: {metrics['error_rate']:.2%}",
        f"- Avg latency ms: {metrics['avg_latency_ms']}",
        f"- P95 latency ms: {metrics['p95_latency_ms']}",
        f"- Avg prompt tokens: {metrics['avg_prompt_tokens']}",
        f"- Total prompt tokens: {metrics['total_prompt_tokens']}",
        "",
        "## Cases",
        "",
    ]

    for result in report["cases"]:
        lines.extend(
            [
                f"### {result['case_id']}",
                "",
                f"- Passed: `{result['passed']}`",
                f"- Failures: {', '.join(result['failures']) or 'none'}",
                f"- Trace ID: `{result['trace_id']}`",
                f"- Actual tools: `{result['actual_tools']}`",
                f"- RAG hit: `{result['rag_hit']}`",
                f"- Latency ms: {result['latency_ms']}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def percentile(values: list[int], percentile_value: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile_value / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return numerator / denominator


def _remove_path_best_effort(path: Path) -> None:
    for _ in range(3):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(0.1)


if __name__ == "__main__":
    eval_report = run_eval()
    print(json.dumps(eval_report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if eval_report["passed"] else 1)
