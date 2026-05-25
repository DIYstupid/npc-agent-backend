import re
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main as main_api
from app.api import chat as chat_api
from app.api import debug as debug_api
from app.api import memory as memory_api
from app.data.seed import NPCS, PLAYERS
from app.main import app
from app.schemas.chat import AgentAction, ChatMessage
from app.schemas.game import PlayerState
from app.schemas.llm import LLMChatResult
from app.schemas.memory import LongTermMemory
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.trace import PromptTraceRecord, PromptTraceSummary
from app.services.chat_service import ChatService
from app.services.context_builder_service import ContextBuilderService
from app.services.reflection_service import ReflectionService
from app.services.reflection_worker import ReflectionWorker
from app.services.token_budget_service import TokenBudgetService
from app.services.tool_service import ToolService


class IntegrationLLMClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self._lock = threading.Lock()

    def generate(self, prompt: str) -> LLMChatResult:
        player_match = re.search(r"player_\d+", prompt)
        player_id = player_match.group(0) if player_match else "player_001"
        quest_id = f"fetch_iron_ore_{player_id}"
        with self._lock:
            self.prompts.append(prompt)

        return LLMChatResult(
            reply=f"Bring me iron ore, {player_id}, and I will repair your sword.",
            actions=[
                AgentAction(
                    tool="create_quest",
                    args={"quest_id": quest_id},
                )
            ],
        )


class SharedKnowledgeAwareLLMClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> LLMChatResult:
        self.prompts.append(prompt)
        if "The tavern keeper is looking for Gary." in prompt:
            return LLMChatResult(
                reply="The tavern keeper is indeed looking for you.",
                actions=[],
            )

        return LLMChatResult(
            reply="I have not heard anything about that.",
            actions=[],
        )


class IntegrationGameService:
    def __init__(self, players: list[PlayerState] | None = None) -> None:
        players = players or [PLAYERS[0]]
        self.players: dict[str, PlayerState] = {
            player.player_id: player.model_copy(deep=True)
            for player in players
        }
        self._lock = threading.Lock()

    def get_player_state(self, player_id: str) -> PlayerState | None:
        with self._lock:
            player = self.players.get(player_id)
            if player is None:
                return None
            return player.model_copy(deep=True)

    def save_player_state(self, player_state: PlayerState) -> None:
        with self._lock:
            self.players[player_state.player_id] = player_state.model_copy(deep=True)

    def create_quest(self, player_id: str, quest_id: str) -> bool:
        with self._lock:
            player = self.players.get(player_id)
            if player is None:
                return False

            if quest_id not in player.active_quests and quest_id not in player.completed_quests:
                player.active_quests.append(quest_id)

            self.players[player_id] = player
            return True


class IntegrationMemoryService:
    def __init__(self) -> None:
        self.messages: dict[tuple[str, str], list[ChatMessage]] = {}
        self.summaries: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def get_messages(self, player_id: str, npc_id: str) -> list[ChatMessage]:
        with self._lock:
            return list(self.messages.get((player_id, npc_id), []))

    def get_summary(self, player_id: str, npc_id: str) -> str:
        with self._lock:
            return self.summaries.get((player_id, npc_id), "")

    def add_message(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
    ) -> None:
        with self._lock:
            self.messages.setdefault((player_id, npc_id), []).append(
                ChatMessage(role=role, content=content)
            )

    def clear_messages(self, player_id: str, npc_id: str) -> None:
        with self._lock:
            self.messages.pop((player_id, npc_id), None)


class IntegrationLongTermMemoryService:
    def __init__(self) -> None:
        self.memories: dict[str, LongTermMemory] = {}
        self._lock = threading.Lock()

    def add_memory(
        self,
        npc_id: str,
        player_id: str,
        text: str,
        importance: int = 1,
        memory_type: str = "general",
        tags: list[str] | None = None,
    ) -> LongTermMemory:
        memory = LongTermMemory(
            memory_id=str(uuid.uuid4()),
            npc_id=npc_id,
            player_id=player_id,
            text=text,
            importance=importance,
            memory_type=memory_type,
            tags=list(tags or []),
            created_at="2026-05-09T00:00:00Z",
        )
        with self._lock:
            self.memories[memory.memory_id] = memory
        return memory

    def list_memories(
        self,
        npc_id: str,
        player_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        with self._lock:
            memories = [
                memory
                for memory in self.memories.values()
                if memory.npc_id == npc_id
                and memory.player_id == player_id
                and (memory_type is None or memory.memory_type == memory_type)
            ]
        return memories[:limit]

    def search_memory(
        self,
        npc_id: str,
        player_id: str,
        query: str,
        top_k: int = 3,
        memory_type: str | None = None,
    ) -> list[LongTermMemory]:
        memories = self.list_memories(
            npc_id=npc_id,
            player_id=player_id,
            memory_type=memory_type,
            limit=100,
        )
        matching = [
            memory
            for memory in memories
            if query in memory.text or memory.text in query or query in memory.tags
        ]
        return matching[:top_k]


class IntegrationSharedKnowledgeService:
    def __init__(self) -> None:
        self.events: dict[str, KnowledgeEvent] = {}
        self._lock = threading.Lock()

    def publish_event(
        self,
        text: str,
        player_id: str | None = None,
        world_id: str = "default",
        scope: str = "player",
        related_player_ids: list[str] | None = None,
        source_npc_id: str | None = None,
        subject_npc_ids: list[str] | None = None,
        known_by_npc_ids: list[str] | None = None,
        location: str | None = None,
        event_type: str = "general",
        confidence: float = 1.0,
        status: str = "active",
        expires_at: str | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeEvent:
        event = KnowledgeEvent(
            event_id=str(uuid.uuid4()),
            world_id=world_id,
            scope=scope,
            player_id=player_id,
            related_player_ids=list(related_player_ids or ([player_id] if player_id else [])),
            text=text,
            source_npc_id=source_npc_id,
            subject_npc_ids=list(subject_npc_ids or []),
            known_by_npc_ids=list(known_by_npc_ids or []),
            location=location,
            event_type=event_type,
            confidence=confidence,
            status=status,
            expires_at=expires_at,
            tags=list(tags or []),
        )
        with self._lock:
            self.events[event.event_id] = event
        return event

    def get_relevant_events(
        self,
        player_id: str,
        npc_id: str,
        query: str,
        world_id: str = "default",
        top_k: int = 5,
    ) -> list[KnowledgeEvent]:
        with self._lock:
            events = list(self.events.values())

        return [
            event
            for event in events
            if event.world_id == world_id
            and event.status == "active"
            and (
                event.scope == "world"
                or event.player_id == player_id
                or player_id in event.related_player_ids
            )
            and (
                npc_id == event.source_npc_id
                or npc_id in event.subject_npc_ids
                or npc_id in event.known_by_npc_ids
            )
        ][:top_k]

    def list_events(
        self,
        world_id: str = "default",
        player_id: str | None = None,
        npc_id: str | None = None,
        status: str | None = "active",
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        with self._lock:
            events = list(self.events.values())
        return events[:limit]


class IntegrationTraceService:
    def __init__(self) -> None:
        self.records: list[PromptTraceRecord] = []
        self._lock = threading.Lock()

    def save_chat_trace(self, **kwargs) -> None:
        with self._lock:
            self.records.append(
                PromptTraceRecord(
                    created_at="2026-05-09T00:00:00Z",
                    **kwargs,
                )
            )

    def list_traces(self, limit: int = 20) -> list[PromptTraceSummary]:
        with self._lock:
            records = list(self.records)

        summaries = [
            PromptTraceSummary(
                request_id=record.request_id,
                created_at=record.created_at,
                npc_id=record.npc_id,
                player_id=record.player_id,
                message_preview=record.message[:80],
                estimated_prompt_tokens=record.context_report.estimated_prompt_tokens,
                estimated_saved_tokens=record.context_report.estimated_saved_tokens,
                actions_count=len(record.actions),
                executed_actions_count=len(record.executed_actions),
                elapsed_ms=record.elapsed_ms,
                error=record.error,
            )
            for record in records
        ]
        return summaries[-limit:]

    def latest_trace(self) -> PromptTraceRecord | None:
        with self._lock:
            if not self.records:
                return None
            return self.records[-1]

    def get_trace(self, request_id: str) -> PromptTraceRecord | None:
        with self._lock:
            records = list(self.records)

        for record in records:
            if record.request_id == request_id:
                return record
        return None


def build_integration_chat_service(
    llm_client: IntegrationLLMClient,
    memory_service: IntegrationMemoryService,
    long_term_memory_service: IntegrationLongTermMemoryService,
    shared_knowledge_service: IntegrationSharedKnowledgeService,
    game_service: IntegrationGameService,
    trace_service: IntegrationTraceService,
) -> ChatService:
    reflection_worker = ReflectionWorker(
        reflection_service=ReflectionService(),
        long_term_memory_service=long_term_memory_service,
        mode="sync",
    )
    service = ChatService.__new__(ChatService)
    service.llm_client = llm_client
    service.memory_service = memory_service
    service.long_term_memory_service = long_term_memory_service
    service.shared_knowledge_service = shared_knowledge_service
    service.tool_service = ToolService(
        game_service=game_service,
        shared_knowledge_service=shared_knowledge_service,
    )
    service.reflection_service = ReflectionService()
    service.reflection_worker = reflection_worker
    service.context_builder_service = ContextBuilderService(
        token_budget_service=TokenBudgetService()
    )
    service.trace_service = trace_service
    return service


class ChatIntegrationTests(unittest.TestCase):
    def test_chat_endpoint_runs_full_pipeline_and_exposes_side_effects(self) -> None:
        client = TestClient(app)
        llm_client = IntegrationLLMClient()
        game_service = IntegrationGameService()
        memory_service = IntegrationMemoryService()
        long_term_memory_service = IntegrationLongTermMemoryService()
        shared_knowledge_service = IntegrationSharedKnowledgeService()
        trace_service = IntegrationTraceService()
        chat_service = build_integration_chat_service(
            llm_client=llm_client,
            memory_service=memory_service,
            long_term_memory_service=long_term_memory_service,
            shared_knowledge_service=shared_knowledge_service,
            game_service=game_service,
            trace_service=trace_service,
        )

        with patch.object(chat_api, "game_service", game_service), patch.object(
            chat_api,
            "memory_service",
            memory_service,
        ), patch.object(
            chat_api,
            "chat_service",
            chat_service,
        ), patch.object(
            memory_api,
            "long_term_memory_service",
            long_term_memory_service,
        ), patch.object(
            memory_api,
            "memory_service",
            memory_service,
        ), patch.object(
            debug_api,
            "trace_service",
            trace_service,
        ), patch.object(
            chat_api,
            "shared_knowledge_service",
            shared_knowledge_service,
        ), patch.object(
            main_api,
            "game_service",
            game_service,
        ):
            chat_response = client.post(
                f"/chat/{NPCS[0].npc_id}",
                json={
                    "player_id": PLAYERS[0].player_id,
                    "message": "My sword is broken.",
                },
            )
            self.assertEqual(chat_response.status_code, 200)
            chat_payload = chat_response.json()
            self.assertEqual(
                chat_payload["reply"],
                "Bring me iron ore, player_001, and I will repair your sword.",
            )
            self.assertEqual(chat_payload["actions"][0]["tool"], "create_quest")
            self.assertEqual(chat_payload["executed_actions"][0]["success"], True)
            self.assertEqual(
                chat_payload["executed_actions"][0]["data"]["quest_id"],
                "fetch_iron_ore_player_001",
            )

            state_response = client.get(f"/game/state/{PLAYERS[0].player_id}")
            self.assertEqual(state_response.status_code, 200)
            self.assertIn(
                "fetch_iron_ore_player_001",
                state_response.json()["active_quests"],
            )

            history_response = client.get(
                f"/chat/history/{PLAYERS[0].player_id}/{NPCS[0].npc_id}"
            )
            self.assertEqual(history_response.status_code, 200)
            self.assertEqual(
                [(message["role"], message["content"]) for message in history_response.json()["messages"]],
                [
                    ("player", "My sword is broken."),
                    ("npc", "Bring me iron ore, player_001, and I will repair your sword."),
                ],
            )

            memory_response = client.get(
                "/memory/long-term",
                params={
                    "npc_id": NPCS[0].npc_id,
                    "player_id": PLAYERS[0].player_id,
                    "memory_type": "quest",
                },
            )
            self.assertEqual(memory_response.status_code, 200)
            memories = memory_response.json()["memories"]
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0]["memory_type"], "quest")
            self.assertEqual(memories[0]["tags"], ["reflection"])

            trace_response = client.get("/debug/traces/latest")
            self.assertEqual(trace_response.status_code, 200)
            trace_payload = trace_response.json()
            self.assertEqual(trace_payload["reply"], chat_payload["reply"])
            self.assertEqual(trace_payload["actions"][0]["tool"], "create_quest")
            self.assertEqual(trace_payload["validated_actions"][0]["tool"], "create_quest")

        self.assertEqual(len(llm_client.prompts), 1)
        self.assertIn("My sword is broken.", llm_client.prompts[0])

    def test_concurrent_players_are_isolated_for_same_npc(self) -> None:
        players = [
            PLAYERS[0].model_copy(
                deep=True,
                update={
                    "player_id": f"player_{index:03d}",
                    "name": f"Player{index}",
                    "active_quests": [],
                    "completed_quests": [],
                    "inventory": ["old_sword"],
                    "relationships": {NPCS[0].npc_id: 0},
                },
            )
            for index in range(101, 106)
        ]
        llm_client = IntegrationLLMClient()
        game_service = IntegrationGameService(players=players)
        memory_service = IntegrationMemoryService()
        long_term_memory_service = IntegrationLongTermMemoryService()
        shared_knowledge_service = IntegrationSharedKnowledgeService()
        trace_service = IntegrationTraceService()
        chat_service = build_integration_chat_service(
            llm_client=llm_client,
            memory_service=memory_service,
            long_term_memory_service=long_term_memory_service,
            shared_knowledge_service=shared_knowledge_service,
            game_service=game_service,
            trace_service=trace_service,
        )

        def post_chat(player: PlayerState) -> dict:
            local_client = TestClient(app)
            response = local_client.post(
                f"/chat/{NPCS[0].npc_id}",
                json={
                    "player_id": player.player_id,
                    "message": f"My sword is broken from {player.player_id}.",
                },
            )
            self.assertEqual(response.status_code, 200)
            return response.json()

        with patch.object(chat_api, "game_service", game_service), patch.object(
            chat_api,
            "memory_service",
            memory_service,
        ), patch.object(
            chat_api,
            "chat_service",
            chat_service,
        ), patch.object(
            memory_api,
            "long_term_memory_service",
            long_term_memory_service,
        ), patch.object(
            memory_api,
            "memory_service",
            memory_service,
        ), patch.object(
            debug_api,
            "trace_service",
            trace_service,
        ), patch.object(
            chat_api,
            "shared_knowledge_service",
            shared_knowledge_service,
        ), patch.object(
            main_api,
            "game_service",
            game_service,
        ):
            with ThreadPoolExecutor(max_workers=len(players)) as executor:
                responses = list(executor.map(post_chat, players))

            self.assertEqual(len(responses), len(players))
            for player, payload in zip(players, responses):
                expected_quest = f"fetch_iron_ore_{player.player_id}"
                self.assertEqual(payload["player_id"], player.player_id)
                self.assertEqual(payload["npc_id"], NPCS[0].npc_id)
                self.assertEqual(payload["actions"][0]["args"]["quest_id"], expected_quest)
                self.assertEqual(
                    payload["executed_actions"][0]["data"]["quest_id"],
                    expected_quest,
                )

            verification_client = TestClient(app)
            all_expected_quests = {
                f"fetch_iron_ore_{player.player_id}"
                for player in players
            }
            for player in players:
                expected_quest = f"fetch_iron_ore_{player.player_id}"
                other_quests = all_expected_quests - {expected_quest}

                state_response = verification_client.get(
                    f"/game/state/{player.player_id}"
                )
                self.assertEqual(state_response.status_code, 200)
                active_quests = set(state_response.json()["active_quests"])
                self.assertIn(expected_quest, active_quests)
                self.assertTrue(active_quests.isdisjoint(other_quests))

                history_response = verification_client.get(
                    f"/chat/history/{player.player_id}/{NPCS[0].npc_id}"
                )
                self.assertEqual(history_response.status_code, 200)
                history = history_response.json()["messages"]
                self.assertEqual(len(history), 2)
                self.assertEqual(
                    history[0],
                    {
                        "role": "player",
                        "content": f"My sword is broken from {player.player_id}.",
                    },
                )
                self.assertIn(player.player_id, history[1]["content"])

                memory_response = verification_client.get(
                    "/memory/long-term",
                    params={
                        "npc_id": NPCS[0].npc_id,
                        "player_id": player.player_id,
                        "memory_type": "quest",
                    },
                )
                self.assertEqual(memory_response.status_code, 200)
                memories = memory_response.json()["memories"]
                self.assertEqual(len(memories), 1)
                self.assertEqual(memories[0]["player_id"], player.player_id)
                self.assertIn(expected_quest, memories[0]["text"])

            traces_response = verification_client.get(
                "/debug/traces",
                params={"limit": len(players)},
            )
            self.assertEqual(traces_response.status_code, 200)
            trace_player_ids = {
                trace["player_id"]
                for trace in traces_response.json()["traces"]
            }
            self.assertEqual(
                trace_player_ids,
                {player.player_id for player in players},
            )

        self.assertEqual(len(llm_client.prompts), len(players))

    def test_shared_knowledge_reaches_subject_npc_and_stays_player_scoped(self) -> None:
        tavernkeeper = NPCS[0].model_copy(
            update={
                "npc_id": "tavernkeeper_001",
                "name": "Mira",
                "role": "tavern keeper",
                "location": "tavern",
            }
        )
        player_two = PLAYERS[0].model_copy(
            deep=True,
            update={
                "player_id": "player_002",
                "name": "OtherPlayer",
            },
        )
        llm_client = SharedKnowledgeAwareLLMClient()
        game_service = IntegrationGameService(players=[PLAYERS[0], player_two])
        memory_service = IntegrationMemoryService()
        long_term_memory_service = IntegrationLongTermMemoryService()
        shared_knowledge_service = IntegrationSharedKnowledgeService()
        trace_service = IntegrationTraceService()
        chat_service = build_integration_chat_service(
            llm_client=llm_client,
            memory_service=memory_service,
            long_term_memory_service=long_term_memory_service,
            shared_knowledge_service=shared_knowledge_service,
            game_service=game_service,
            trace_service=trace_service,
        )
        shared_knowledge_service.publish_event(
            text="The tavern keeper is looking for Gary.",
            player_id=PLAYERS[0].player_id,
            source_npc_id="tavernkeeper_001",
            subject_npc_ids=["tavernkeeper_001"],
            known_by_npc_ids=[NPCS[0].npc_id],
            event_type="request",
        )

        response_for_player_one = chat_service.chat(
            npc=tavernkeeper,
            player_state=PLAYERS[0],
            message="Are you looking for me?",
        )
        first_trace = trace_service.latest_trace()
        response_for_player_two = chat_service.chat(
            npc=tavernkeeper,
            player_state=player_two,
            message="Are you looking for me?",
        )
        latest_trace = trace_service.latest_trace()

        self.assertEqual(
            response_for_player_one.reply,
            "The tavern keeper is indeed looking for you.",
        )
        self.assertEqual(
            response_for_player_one.context_report.selected_shared_knowledge_events,
            1,
        )
        self.assertEqual(
            response_for_player_two.reply,
            "I have not heard anything about that.",
        )
        self.assertEqual(
            response_for_player_two.context_report.selected_shared_knowledge_events,
            0,
        )
        self.assertEqual(len(first_trace.selected_shared_knowledge), 1)
        self.assertEqual(latest_trace.selected_shared_knowledge, [])
        self.assertIn("The tavern keeper is looking for Gary.", llm_client.prompts[0])
        self.assertNotIn("The tavern keeper is looking for Gary.", llm_client.prompts[1])


if __name__ == "__main__":
    unittest.main()
