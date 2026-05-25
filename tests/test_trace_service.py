import unittest
import uuid
from pathlib import Path

from app.schemas.context import ContextReport
from app.services.trace_service import TraceService


class TraceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"traces_{uuid.uuid4().hex}.db"
        self.trace_service = TraceService(db_path=str(self.db_path), max_records=10)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_save_and_read_prompt_trace(self) -> None:
        self.trace_service.save_chat_trace(
            request_id="trace_001",
            npc_id="blacksmith_001",
            player_id="player_001",
            message="repair sword",
            reply="bring ore",
            prompt="prompt text",
            context_report=ContextReport(
                request_id="trace_001",
                token_budget=3000,
                estimated_prompt_tokens=120,
                estimated_saved_tokens=30,
            ),
            actions=[],
            executed_actions=[],
            selected_short_term_memory=[],
            selected_long_term_memory=[],
            summary_memory="",
            elapsed_ms=42,
        )

        trace = self.trace_service.get_trace("trace_001")
        latest = self.trace_service.latest_trace()
        summaries = self.trace_service.list_traces(limit=5)

        self.assertIsNotNone(trace)
        self.assertEqual(trace.request_id, "trace_001")
        self.assertEqual(latest.request_id, "trace_001")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].estimated_prompt_tokens, 120)

    def test_save_and_read_agent_trace(self) -> None:
        self.trace_service.save_agent_trace(
            request_id="quest_trace_001",
            agent_type="quest_agent",
            player_id="player_001",
            message="create quest unit_test_quest",
            reply="Quest created: unit_test_quest",
            agent_state={
                "quest_id": "unit_test_quest",
                "status": "created",
            },
            elapsed_ms=12,
        )

        trace = self.trace_service.get_trace("quest_trace_001")
        summaries = self.trace_service.list_traces(limit=5)

        self.assertIsNotNone(trace)
        self.assertEqual(trace.agent_type, "quest_agent")
        self.assertEqual(trace.npc_id, "quest_agent")
        self.assertEqual(trace.agent_state["quest_id"], "unit_test_quest")
        self.assertEqual(summaries[0].agent_type, "quest_agent")


if __name__ == "__main__":
    unittest.main()
