import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import debug as debug_api
from app.api import quest as quest_api
from app.api import world as world_api
from app.main import app
from app.schemas.game import PlayerState, QuestProgressUpdate
from app.schemas.quest import QuestAgentResponse
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.trace import PromptTraceSummary
from app.schemas.world import WorldActionResponse, WorldAgentResponse, WorldInteractionResponse


class FakeQuestAgent:
    async def ainvoke(self, request) -> QuestAgentResponse:
        return QuestAgentResponse(
            request_id="quest_trace_001",
            player_id=request.player_id,
            quest_id=request.quest_id,
            operation=request.operation,
            status="created",
            message=f"Quest created: {request.quest_id}",
            executed_actions=[],
            player_state=PlayerState(
                player_id=request.player_id,
                name="Gary",
                location="village_square",
                active_quests=[request.quest_id],
            ),
        )


class FakeWorldAgent:
    async def ainvoke(self, request) -> WorldAgentResponse:
        event = KnowledgeEvent(
            event_id="event_001",
            world_id=request.world_id,
            scope=request.scope,
            player_id=request.player_id,
            text=request.text,
            event_type=request.event_type,
            status="active",
        )
        return WorldAgentResponse(
            request_id="world_trace_001",
            world_id=request.world_id,
            player_id=request.player_id,
            status="published",
            message="World event published: event_001",
            event=event,
            executed_actions=[],
        )

    async def interact(self, request) -> WorldInteractionResponse:
        event = KnowledgeEvent(
            event_id="event_interaction_001",
            world_id=request.world_id,
            scope="player",
            player_id=request.player_id,
            text=request.text,
            event_type="talk_to_npc",
            status="active",
        )
        return WorldInteractionResponse(
            request_id="world_interaction_001",
            world_id=request.world_id,
            player_id=request.player_id,
            status="applied",
            message="World interaction applied; quests advanced: unit_test_quest",
            events=[event],
            quest_updates=[
                QuestProgressUpdate(
                    quest_id="unit_test_quest",
                    status="advanced",
                    completed_objectives=["report_to_guard"],
                    remaining_objectives=[],
                    message="Quest advanced: unit_test_quest",
                )
            ],
            player_state=PlayerState(
                player_id=request.player_id,
                name="Gary",
                location="village_square",
                active_quests=["unit_test_quest"],
            ),
        )


class FakeWorldActionService:
    async def apply_action(self, request) -> WorldActionResponse:
        return WorldActionResponse(
            request_id="world_action_001",
            player_id=request.player_id,
            action_type=request.action_type,
            status="applied",
            message="World action applied; quests advanced: unit_test_quest",
            event=KnowledgeEvent(
                event_id="event_action_001",
                world_id=request.world_id,
                scope="player",
                player_id=request.player_id,
                text="Player inspected wolf tracks.",
                event_type=request.action_type,
                status="active",
            ),
            executed_actions=[],
            quest_updates=[
                QuestProgressUpdate(
                    quest_id="unit_test_quest",
                    status="advanced",
                    completed_objectives=["inspect_tracks"],
                    remaining_objectives=["report_to_guard"],
                    message="Quest advanced: unit_test_quest",
                )
            ],
            player_state=PlayerState(
                player_id=request.player_id,
                name="Gary",
                location="north_road",
                active_quests=["unit_test_quest"],
            ),
        )


class FakeGameService:
    def get_player_state(self, player_id: str) -> PlayerState | None:
        if player_id != "player_001":
            return None
        return PlayerState(
            player_id=player_id,
            name="Gary",
            location="village_square",
            active_quests=["unit_test_quest"],
            completed_quests=[],
        )


class FakeSharedKnowledgeService:
    def list_events(self, **kwargs) -> list[KnowledgeEvent]:
        return [
            KnowledgeEvent(
                event_id="event_001",
                world_id=kwargs.get("world_id", "default"),
                scope="world",
                text="The old tower bell rings at midnight.",
                event_type="rumor",
                status="active",
            )
        ]


class FakeTraceService:
    def list_traces(self, limit: int = 20) -> list[PromptTraceSummary]:
        return [
            PromptTraceSummary(
                request_id="quest_trace_001",
                created_at="2026-05-11T00:00:00Z",
                agent_type="quest_agent",
                npc_id="quest_agent",
                player_id="player_001",
                message_preview="create quest unit_test_quest",
                estimated_prompt_tokens=0,
                estimated_saved_tokens=0,
                actions_count=1,
                executed_actions_count=1,
                elapsed_ms=1,
            )
        ]


class Phase3AgentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_quest_agent_routes(self) -> None:
        with patch.object(quest_api, "quest_agent", FakeQuestAgent()), patch.object(
            quest_api,
            "game_service",
            FakeGameService(),
        ):
            create_response = self.client.post("/quest/player_001/unit_test_quest/create")
            state_response = self.client.get("/quest/player_001")

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["status"], "created")
        self.assertEqual(create_response.json()["player_state"]["active_quests"], ["unit_test_quest"])
        self.assertEqual(state_response.status_code, 200)
        self.assertEqual(state_response.json()["active_quests"], ["unit_test_quest"])

    def test_world_agent_routes_and_trace_agent_type(self) -> None:
        with patch.object(world_api, "world_agent", FakeWorldAgent()), patch.object(
            world_api,
            "world_action_service",
            FakeWorldActionService(),
        ), patch.object(
            world_api,
            "shared_knowledge_service",
            FakeSharedKnowledgeService(),
        ), patch.object(
            debug_api,
            "trace_service",
            FakeTraceService(),
        ):
            create_response = self.client.post(
                "/world/events",
                json={
                    "text": "The old tower bell rings at midnight.",
                    "event_type": "rumor",
                },
            )
            timeline_response = self.client.get("/world/events", params={"event_type": "rumor"})
            action_response = self.client.post(
                "/world/actions",
                json={
                    "player_id": "player_001",
                    "action_type": "inspect_object",
                    "target_id": "wolf_tracks",
                    "location": "north_road",
                },
            )
            interaction_response = self.client.post(
                "/world/interactions",
                json={
                    "player_id": "player_001",
                    "text": "我向守卫队长汇报调查结果。",
                    "npc_id": "guard_001",
                },
            )
            traces_response = self.client.get("/debug/traces")

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["status"], "published")
        self.assertEqual(create_response.json()["event"]["event_id"], "event_001")
        self.assertEqual(timeline_response.status_code, 200)
        self.assertEqual(len(timeline_response.json()["events"]), 1)
        self.assertEqual(action_response.status_code, 200)
        self.assertEqual(action_response.json()["status"], "applied")
        self.assertEqual(action_response.json()["quest_updates"][0]["completed_objectives"], ["inspect_tracks"])
        self.assertEqual(interaction_response.status_code, 200)
        self.assertEqual(interaction_response.json()["status"], "applied")
        self.assertEqual(interaction_response.json()["quest_updates"][0]["completed_objectives"], ["report_to_guard"])
        self.assertEqual(traces_response.status_code, 200)
        self.assertEqual(traces_response.json()["traces"][0]["agent_type"], "quest_agent")


if __name__ == "__main__":
    unittest.main()
