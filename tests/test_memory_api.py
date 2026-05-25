import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api import debug as debug_api
from app.api import memory as memory_api
from app.main import app
from app.schemas.chat import ChatMessage
from app.schemas.context import ContextReport
from app.schemas.game import PlayerState
from app.schemas.memory import LongTermMemory
from app.schemas.trace import PromptTraceRecord, PromptTraceSummary


class FakeLongTermMemoryService:
    def __init__(self) -> None:
        self.memories: dict[str, LongTermMemory] = {}

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
            memory_type=memory_type,
            importance=importance,
            created_at="2026-05-07T00:00:00Z",
            tags=list(tags or []),
        )
        self.memories[memory.memory_id] = memory
        return memory

    def list_memories(
        self,
        npc_id: str,
        player_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        memories = [
            memory
            for memory in self.memories.values()
            if memory.npc_id == npc_id
            and memory.player_id == player_id
            and (memory_type is None or memory.memory_type == memory_type)
        ]
        memories = sorted(
            memories,
            key=lambda memory: (memory.created_at or "", memory.importance, memory.memory_id),
            reverse=True,
        )
        return memories[: max(1, limit)]

    def search_memory(
        self,
        npc_id: str,
        player_id: str,
        query: str,
        top_k: int = 3,
        memory_type: str | None = None,
    ) -> list[LongTermMemory]:
        query_lower = query.lower()
        query_terms = {
            query_lower[index : index + 2]
            for index in range(max(0, len(query_lower) - 1))
            if not query_lower[index : index + 2].isspace()
        }
        memories = [
            memory
            for memory in self.list_memories(
                npc_id=npc_id,
                player_id=player_id,
                memory_type=memory_type,
                limit=100,
            )
            if self._matches_query(memory, query_lower, query_terms)
        ]
        return memories[: max(1, top_k)]

    def _matches_query(
        self,
        memory: LongTermMemory,
        query_lower: str,
        query_terms: set[str],
    ) -> bool:
        searchable = " ".join([memory.text, *memory.tags]).lower()
        if query_lower in searchable:
            return True

        return any(term in searchable for term in query_terms)

    def update_memory(
        self,
        memory_id: str,
        text: str | None = None,
        importance: int | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
    ) -> LongTermMemory | None:
        existing = self.memories.get(memory_id)
        if existing is None:
            return None

        updated = existing.model_copy(
            update={
                "text": text if text is not None else existing.text,
                "importance": importance if importance is not None else existing.importance,
                "memory_type": memory_type if memory_type is not None else existing.memory_type,
                "tags": list(tags) if tags is not None else existing.tags,
            }
        )
        self.memories[memory_id] = updated
        return updated

    def delete_memory(self, memory_id: str) -> bool:
        return self.memories.pop(memory_id, None) is not None


class FakeMemoryService:
    def __init__(self) -> None:
        self.messages: dict[tuple[str, str], list[ChatMessage]] = {
            (
                "player_001",
                "blacksmith_001",
            ): [
                ChatMessage(role="player", content="昨天我提到银矿石。"),
                ChatMessage(role="npc", content="如果你能带来银矿石，我就修好它。"),
            ]
        }
        self.summaries: dict[tuple[str, str], str] = {
            ("player_001", "blacksmith_001"): "玩家答应为铁匠寻找银矿石。",
        }

    def get_messages(self, player_id: str, npc_id: str) -> list[ChatMessage]:
        return self.messages.get((player_id, npc_id), [])

    def get_summary(self, player_id: str, npc_id: str) -> str:
        return self.summaries.get((player_id, npc_id), "")


class FakeGameService:
    def __init__(self) -> None:
        self.players = {
            "player_001": PlayerState(
                player_id="player_001",
                name="Gary",
                location="village_square",
                inventory=["old_sword", "bread"],
                active_quests=["investigate_wolves"],
                completed_quests=[],
                world_flags={"wolves_near_village": True},
                relationships={"blacksmith_001": 5},
            )
        }

    def get_player_state(self, player_id: str) -> PlayerState | None:
        return self.players.get(player_id)


class FakeTraceService:
    def __init__(self) -> None:
        self.record = PromptTraceRecord(
            request_id="trace_001",
            created_at="2026-05-07T00:00:00Z",
            npc_id="blacksmith_001",
            player_id="player_001",
            message="repair sword",
            reply="bring ore",
            prompt="prompt text",
            context_report=ContextReport(
                request_id="trace_001",
                token_budget=3000,
                estimated_prompt_tokens=128,
                estimated_saved_tokens=16,
                selected_short_term_messages=2,
                selected_long_term_memories=1,
            ),
            actions=[],
            executed_actions=[],
            selected_short_term_memory=[],
            selected_long_term_memory=[],
            summary_memory="summary text",
            elapsed_ms=42,
            error=None,
        )
        self.summary = PromptTraceSummary(
            request_id="trace_001",
            created_at="2026-05-07T00:00:00Z",
            npc_id="blacksmith_001",
            player_id="player_001",
            message_preview="repair sword",
            estimated_prompt_tokens=128,
            estimated_saved_tokens=16,
            actions_count=0,
            executed_actions_count=0,
            elapsed_ms=42,
            error=None,
        )

    def list_traces(self, limit: int = 20) -> list[PromptTraceSummary]:
        return [self.summary][: max(1, limit)]

    def latest_trace(self) -> PromptTraceRecord | None:
        return self.record

    def get_trace(self, request_id: str) -> PromptTraceRecord | None:
        if request_id == self.record.request_id:
            return self.record
        return None


class MemoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.long_term_memory_service = FakeLongTermMemoryService()
        self.memory_service = FakeMemoryService()
        self.game_service = FakeGameService()
        self.trace_service = FakeTraceService()

    def test_long_term_memory_management_routes(self) -> None:
        with patch.object(
            memory_api,
            "long_term_memory_service",
            self.long_term_memory_service,
        ), patch.object(
            memory_api,
            "memory_service",
            self.memory_service,
        ):
            create_response = self.client.post(
                "/memory/long-term",
                json={
                    "npc_id": "blacksmith_001",
                    "player_id": "player_001",
                    "text": "玩家愿意帮铁匠寻找银矿石。",
                    "importance": 5,
                    "memory_type": "quest",
                    "tags": ["reflection", "quest"],
                },
            )
            self.assertEqual(create_response.status_code, 200)
            created_memory = create_response.json()
            self.assertEqual(created_memory["memory_type"], "quest")
            self.assertEqual(created_memory["tags"], ["reflection", "quest"])

            list_response = self.client.get(
                "/memory/long-term",
                params={
                    "npc_id": "blacksmith_001",
                    "player_id": "player_001",
                    "memory_type": "quest",
                },
            )
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.json()["npc_id"], "blacksmith_001")
            self.assertEqual(len(list_response.json()["memories"]), 1)

            search_response = self.client.get(
                "/memory/long-term/search",
                params={
                    "npc_id": "blacksmith_001",
                    "player_id": "player_001",
                    "query": "银矿石",
                },
            )
            self.assertEqual(search_response.status_code, 200)
            self.assertEqual(len(search_response.json()), 1)

            update_response = self.client.patch(
                f"/memory/long-term/{created_memory['memory_id']}",
                json={
                    "text": "玩家已经接下寻找银矿石的任务。",
                    "importance": 6,
                    "memory_type": "quest",
                    "tags": ["quest", "accepted"],
                },
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertEqual(update_response.json()["importance"], 6)
            self.assertEqual(update_response.json()["tags"], ["quest", "accepted"])

            delete_response = self.client.delete(
                f"/memory/long-term/{created_memory['memory_id']}"
            )
            self.assertEqual(delete_response.status_code, 200)
            self.assertTrue(delete_response.json()["deleted"])

            empty_response = self.client.get(
                "/memory/long-term",
                params={
                    "npc_id": "blacksmith_001",
                    "player_id": "player_001",
                },
            )
            self.assertEqual(empty_response.status_code, 200)
            self.assertEqual(empty_response.json()["memories"], [])

            summary_response = self.client.get(
                "/memory/summary/player_001/blacksmith_001"
            )
            self.assertEqual(summary_response.status_code, 200)
            self.assertIn("银矿石", summary_response.json()["summary"])

    def test_debug_trace_routes(self) -> None:
        with patch.object(debug_api, "trace_service", self.trace_service):
            list_response = self.client.get("/debug/traces", params={"limit": 1})
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(len(list_response.json()["traces"]), 1)

            latest_response = self.client.get("/debug/traces/latest")
            self.assertEqual(latest_response.status_code, 200)
            self.assertEqual(latest_response.json()["request_id"], "trace_001")

            detail_response = self.client.get("/debug/traces/trace_001")
            self.assertEqual(detail_response.status_code, 200)
            self.assertEqual(detail_response.json()["message"], "repair sword")

    def test_debug_prompt_route_builds_context(self) -> None:
        self.long_term_memory_service.add_memory(
            npc_id="blacksmith_001",
            player_id="player_001",
            text="玩家曾经答应寻找银矿石。",
            importance=5,
            memory_type="quest",
            tags=["reflection", "quest"],
        )

        with patch.object(
            chat_api,
            "memory_service",
            self.memory_service,
        ), patch.object(
            chat_api,
            "long_term_memory_service",
            self.long_term_memory_service,
        ), patch.object(
            chat_api,
            "game_service",
            self.game_service,
        ):
            response = self.client.post(
                "/chat/blacksmith_001/debug-prompt",
                json={
                    "player_id": "player_001",
                    "message": "我愿意帮你找银矿石。",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["npc_id"], "blacksmith_001")
        self.assertEqual(payload["player_id"], "player_001")
        self.assertIn("[quest]", payload["prompt"])
        self.assertIn("银矿石", payload["prompt"])
        self.assertEqual(payload["context_report"]["request_id"], "debug-prompt")


if __name__ == "__main__":
    unittest.main()
