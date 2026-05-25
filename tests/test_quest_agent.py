import unittest
import uuid
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.quest_agent import QuestAgent
from app.repositories.player_state_repository import PlayerStateRepository
from app.schemas.quest import QuestAgentRequest
from app.services.game_service import GameService
from app.services.tool_service import ToolService


class FakeTraceService:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def save_agent_trace(self, **kwargs) -> None:
        self.records.append(kwargs)


class QuestAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"quest_agent_{uuid.uuid4().hex}.db"
        self.game_service = GameService(
            PlayerStateRepository(db_path=str(self.db_path))
        )
        self.trace_service = FakeTraceService()
        self.agent = QuestAgent(
            tool_service=ToolService(self.game_service),
            game_service=self.game_service,
            trace_service=self.trace_service,
            checkpointer=InMemorySaver(),
        )

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()

    async def test_create_and_complete_quest(self) -> None:
        create_response = await self.agent.ainvoke(
            QuestAgentRequest(
                player_id="player_001",
                quest_id="unit_test_quest",
                operation="create",
            )
        )
        complete_response = await self.agent.ainvoke(
            QuestAgentRequest(
                player_id="player_001",
                quest_id="unit_test_quest",
                operation="complete",
            )
        )
        player = self.game_service.get_player_state("player_001")

        self.assertEqual(create_response.status, "created")
        self.assertEqual(create_response.executed_actions[0].tool, "create_quest")
        self.assertEqual(complete_response.status, "completed")
        self.assertNotIn("unit_test_quest", player.active_quests)
        self.assertIn("unit_test_quest", player.completed_quests)
        self.assertEqual(len(self.trace_service.records), 2)
        self.assertEqual(self.trace_service.records[-1]["agent_type"], "quest_agent")

    async def test_invalid_operation_does_not_execute_tool(self) -> None:
        response = await self.agent.ainvoke(
            QuestAgentRequest(
                player_id="player_001",
                quest_id="unit_test_quest",
                operation="delete",
            )
        )

        self.assertEqual(response.status, "invalid_operation")
        self.assertEqual(response.executed_actions, [])
        self.assertEqual(self.trace_service.records[0]["agent_state"]["status"], "invalid_operation")


if __name__ == "__main__":
    unittest.main()
