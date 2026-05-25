import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.data.seed import NPCS, PLAYERS
from app.repositories.player_state_repository import PlayerStateRepository
from app.schemas.chat import AgentAction
from app.schemas.context import ContextReport
from app.services.context_builder_service import ContextBuilderService
from app.services.game_service import GameService
from app.services.memory_service import MemoryService
from app.services.token_budget_service import TokenBudgetService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


def run_eval() -> dict:
    results: dict[str, dict] = {}

    memory_service = MemoryService(max_messages=2)
    for index in range(4):
        memory_service.add_message(
            player_id="player_001",
            npc_id="blacksmith_001",
            role="player",
            content=f"eval message {index}",
        )

    summary = memory_service.get_summary("player_001", "blacksmith_001")
    recent_messages = memory_service.get_messages("player_001", "blacksmith_001")
    results["rolling_summary"] = {
        "passed": bool(summary) and len(recent_messages) == 2,
        "summary_chars": len(summary),
        "recent_messages": len(recent_messages),
    }

    context = ContextBuilderService(TokenBudgetService()).build(
        request_id="eval-context",
        npc=NPCS[0],
        player_state=PLAYERS[0],
        player_message="repair sword",
        short_term_memory=recent_messages,
        summary_memory=summary,
        long_term_memory=[],
    )
    results["context_report"] = {
        "passed": context.report.estimated_prompt_tokens > 0,
        "estimated_prompt_tokens": context.report.estimated_prompt_tokens,
        "has_summary_memory": context.report.has_summary_memory,
    }

    tmp_root = REPO_ROOT / "tests" / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    player_db_path = tmp_root / f"eval_player_state_{uuid.uuid4().hex}.db"
    trace_db_path = tmp_root / f"eval_traces_{uuid.uuid4().hex}.db"
    try:
        repository = PlayerStateRepository(
            db_path=str(player_db_path),
        )
        tool_service = ToolService(GameService(repository))
        action = AgentAction(
            tool="create_quest",
            args={"quest_id": "eval_quest"},
        )
        first_result = tool_service.execute_action("player_001", action)
        second_result = tool_service.execute_action("player_001", action)
        results["tool_idempotency"] = {
            "passed": (
                first_result.data.get("status") == "created"
                and second_result.data.get("status") == "already_active"
            ),
            "first_status": first_result.data.get("status"),
            "second_status": second_result.data.get("status"),
        }

        trace_service = TraceService(
            db_path=str(trace_db_path),
            max_records=10,
        )
        trace_service.save_chat_trace(
            request_id="eval-trace",
            npc_id="blacksmith_001",
            player_id="player_001",
            message="repair sword",
            reply="bring ore",
            prompt=context.prompt,
            context_report=ContextReport(
                request_id="eval-trace",
                token_budget=3000,
                estimated_prompt_tokens=context.report.estimated_prompt_tokens,
            ),
            actions=[],
            executed_actions=[],
            selected_short_term_memory=context.selected_short_term_memory,
            selected_long_term_memory=[],
            summary_memory=context.summary_memory,
            elapsed_ms=1,
        )
        results["trace_persistence"] = {
            "passed": trace_service.get_trace("eval-trace") is not None,
            "trace_count": len(trace_service.list_traces()),
        }
    finally:
        for db_path in (player_db_path, trace_db_path):
            for suffix in ("", "-wal", "-shm"):
                path = Path(f"{db_path}{suffix}")
                if path.exists():
                    path.unlink()

    results["passed"] = all(
        item.get("passed", False)
        for key, item in results.items()
        if isinstance(item, dict)
    )
    return results


if __name__ == "__main__":
    eval_results = run_eval()
    print(json.dumps(eval_results, ensure_ascii=False, indent=2))
    raise SystemExit(0 if eval_results["passed"] else 1)
