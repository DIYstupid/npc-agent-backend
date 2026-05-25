import unittest
import uuid
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.world_agent import WorldAgent
from app.repositories.player_state_repository import PlayerStateRepository
from app.repositories.shared_knowledge_repository import SharedKnowledgeRepository
from app.schemas.world import WorldEventCreate, WorldInteractionRequest
from app.services.game_service import GameService
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.tool_service import ToolService
from app.services.world_action_service import WorldActionService


class FakeTraceService:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def save_agent_trace(self, **kwargs) -> None:
        self.records.append(kwargs)


class WorldAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.player_db_path = tmp_root / f"world_agent_player_{uuid.uuid4().hex}.db"
        self.knowledge_db_path = tmp_root / f"world_agent_knowledge_{uuid.uuid4().hex}.db"
        self.game_service = GameService(
            PlayerStateRepository(db_path=str(self.player_db_path))
        )
        self.shared_knowledge_service = SharedKnowledgeService(
            SharedKnowledgeRepository(db_path=str(self.knowledge_db_path))
        )
        self.trace_service = FakeTraceService()
        self.tool_service = ToolService(
            self.game_service,
            shared_knowledge_service=self.shared_knowledge_service,
        )
        self.agent = WorldAgent(
            shared_knowledge_service=self.shared_knowledge_service,
            tool_service=self.tool_service,
            trace_service=self.trace_service,
            checkpointer=InMemorySaver(),
        )
        self.world_action_service = WorldActionService(
            game_service=self.game_service,
            tool_service=self.tool_service,
            world_agent=self.agent,
            trace_service=self.trace_service,
        )
        self.agent.set_world_action_service(self.world_action_service)

    def tearDown(self) -> None:
        for db_path in (self.player_db_path, self.knowledge_db_path):
            for suffix in ("", "-wal", "-shm"):
                path = Path(f"{db_path}{suffix}")
                if path.exists():
                    path.unlink()

    async def test_publish_world_event_and_apply_player_flag(self) -> None:
        response = await self.agent.ainvoke(
            WorldEventCreate(
                text="Wolves gather near the north road.",
                player_id="player_001",
                scope="player",
                source_npc_id="blacksmith_001",
                known_by_npc_ids=["blacksmith_001"],
                event_type="threat",
                world_flags={
                    "wolves_near_north_road": True,
                },
            )
        )
        player = self.game_service.get_player_state("player_001")
        events = self.shared_knowledge_service.list_events(
            player_id="player_001",
            npc_id="blacksmith_001",
            event_type="threat",
        )

        self.assertEqual(response.status, "published")
        self.assertIsNotNone(response.event)
        self.assertEqual(response.executed_actions[0].tool, "set_world_flag")
        self.assertTrue(player.world_flags["wolves_near_north_road"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].text, "Wolves gather near the north road.")
        self.assertEqual(self.trace_service.records[0]["agent_type"], "world_agent")

    async def test_publish_global_event_without_player_flag(self) -> None:
        response = await self.agent.ainvoke(
            WorldEventCreate(
                text="The old tower bell rings at midnight.",
                scope="world",
                event_type="rumor",
            )
        )
        events = self.shared_knowledge_service.list_events(
            event_type="rumor",
        )

        self.assertEqual(response.status, "published")
        self.assertEqual(response.executed_actions, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].scope, "world")

    async def test_interaction_text_applies_verifiable_quest_objectives(self) -> None:
        response = await self.agent.interact(
            WorldInteractionRequest(
                player_id="player_001",
                text="我去北路调查狼群踪迹，然后向守卫队长汇报。",
                npc_id="guard_001",
            )
        )
        player = self.game_service.get_player_state("player_001")

        self.assertEqual(response.status, "applied")
        self.assertEqual([action.action_type for action in response.parsed_actions], ["move", "inspect_object", "talk_to_npc"])
        self.assertIn("investigate_wolves", player.completed_quests)
        self.assertNotIn("investigate_wolves", player.active_quests)
        self.assertEqual(response.quest_updates[-1].status, "completed")
        self.assertTrue(any(record["agent_type"] == "world_agent" for record in self.trace_service.records))

    async def test_interaction_does_not_complete_quest_from_claim_only(self) -> None:
        response = await self.agent.interact(
            WorldInteractionRequest(
                player_id="player_001",
                text="我已经完成任务了。",
                npc_id="guard_001",
            )
        )
        player = self.game_service.get_player_state("player_001")

        self.assertEqual(response.status, "recorded")
        self.assertEqual(response.parsed_actions, [])
        self.assertIn("investigate_wolves", player.active_quests)
        self.assertNotIn("investigate_wolves", player.completed_quests)


if __name__ == "__main__":
    unittest.main()
