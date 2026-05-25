import unittest
import uuid
from pathlib import Path

from app.repositories.player_state_repository import PlayerStateRepository
from app.schemas.chat import AgentAction
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.world import WorldActionRequest, WorldAgentResponse
from app.services.game_service import GameService
from app.services.tool_service import ToolService
from app.services.world_action_service import WorldActionService


class FakeWorldAgent:
    def __init__(self) -> None:
        self.requests = []

    async def ainvoke(self, request) -> WorldAgentResponse:
        self.requests.append(request)
        event = KnowledgeEvent(
            event_id=f"event_{len(self.requests)}",
            world_id=request.world_id,
            scope=request.scope,
            player_id=request.player_id,
            text=request.text,
            event_type=request.event_type,
            status="active",
            tags=request.tags,
        )
        return WorldAgentResponse(
            request_id=f"world_{len(self.requests)}",
            world_id=request.world_id,
            player_id=request.player_id,
            status="published",
            message=f"World event published: {event.event_id}",
            event=event,
            executed_actions=[],
        )


class FakeTraceService:
    def __init__(self) -> None:
        self.records = []

    def save_agent_trace(self, **kwargs) -> None:
        self.records.append(kwargs)


class WorldActionServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"world_action_{uuid.uuid4().hex}.db"
        self.game_service = GameService(
            PlayerStateRepository(db_path=str(self.db_path))
        )
        self.tool_service = ToolService(self.game_service)
        self.world_agent = FakeWorldAgent()
        self.trace_service = FakeTraceService()
        self.service = WorldActionService(
            game_service=self.game_service,
            tool_service=self.tool_service,
            world_agent=self.world_agent,
            trace_service=self.trace_service,
        )

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()

    async def test_world_actions_advance_and_complete_quest_objectives(self) -> None:
        create_result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="create_quest",
                args={
                    "quest_id": "deliver_healing_herb",
                    "objectives": [
                        {
                            "objective_id": "collect_herb",
                            "type": "inventory_contains",
                            "item_id": "healing_herb",
                        },
                        {
                            "objective_id": "deliver_herb",
                            "type": "submit_item_to_npc",
                            "item_id": "healing_herb",
                            "npc_id": "healer_001",
                        },
                    ],
                },
            ),
        )

        pick_response = await self.service.apply_action(
            WorldActionRequest(
                player_id="player_001",
                action_type="pick_item",
                target_id="healing_herb",
                location="forest_edge",
            )
        )
        submit_response = await self.service.apply_action(
            WorldActionRequest(
                player_id="player_001",
                action_type="submit_item_to_npc",
                npc_id="healer_001",
                payload={"item_id": "healing_herb"},
            )
        )
        player = self.game_service.get_player_state("player_001")

        self.assertTrue(create_result.success)
        self.assertEqual(pick_response.status, "applied")
        self.assertEqual(pick_response.quest_updates[0].completed_objectives, ["collect_herb"])
        self.assertEqual(submit_response.status, "applied")
        self.assertEqual(submit_response.quest_updates[0].status, "completed")
        self.assertIn("deliver_healing_herb", player.completed_quests)
        self.assertNotIn("deliver_healing_herb", player.active_quests)
        self.assertNotIn("healing_herb", player.inventory)
        self.assertEqual(len(self.world_agent.requests), 2)
        self.assertEqual(self.trace_service.records[-1]["agent_type"], "world_action")

    async def test_submit_item_rejects_missing_inventory_and_does_not_complete(self) -> None:
        self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="create_quest",
                args={
                    "quest_id": "deliver_missing_herb",
                    "objectives": [
                        {
                            "objective_id": "deliver_herb",
                            "type": "submit_item_to_npc",
                            "item_id": "missing_herb",
                            "npc_id": "healer_001",
                        }
                    ],
                },
            ),
        )

        response = await self.service.apply_action(
            WorldActionRequest(
                player_id="player_001",
                action_type="submit_item_to_npc",
                npc_id="healer_001",
                payload={"item_id": "missing_herb"},
            )
        )
        player = self.game_service.get_player_state("player_001")

        self.assertEqual(response.status, "rejected")
        self.assertEqual(response.executed_actions[0].data["status"], "item_not_found")
        self.assertEqual(response.quest_updates, [])
        self.assertIn("deliver_missing_herb", player.active_quests)
        self.assertNotIn("deliver_missing_herb", player.completed_quests)


if __name__ == "__main__":
    unittest.main()
