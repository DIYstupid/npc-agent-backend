import json
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.data.seed import NPCS, PLAYERS
from app.main import app
from app.schemas.chat import ChatMessage
from app.schemas.context import ContextReport
from app.schemas.llm import LLMChatResult
from app.schemas.reflection import MemoryReflectionResult
from app.services.chat_service import ChatService
from app.services.context_builder_service import BuiltPromptContext
from app.services.reflection_worker import ReflectionJob, ReflectionWorker


def parse_sse_events(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []

    for raw_event in payload.strip().split("\n\n"):
        event_name = ""
        data_lines: list[str] = []

        for line in raw_event.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())

        if event_name:
            events.append((event_name, json.loads("\n".join(data_lines))))

    return events


class FakeLLMClient:
    def generate(self, prompt: str) -> LLMChatResult:
        return LLMChatResult(reply="hello", actions=[])


class FakeMemoryService:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def get_messages(self, player_id: str, npc_id: str) -> list[ChatMessage]:
        return []

    def get_summary(self, player_id: str, npc_id: str) -> str:
        return ""

    def add_message(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
    ) -> None:
        self.messages.append(ChatMessage(role=role, content=content))


class FakeLongTermMemoryService:
    def search_memory(self, **kwargs) -> list:
        return []


class FakeToolService:
    def execute_actions(self, player_id: str, actions: list) -> list:
        return []


class FakeReflectionService:
    def reflect(self, **kwargs) -> MemoryReflectionResult:
        return MemoryReflectionResult(should_remember=False)


class FakeReflectionWorker:
    def __init__(self) -> None:
        self.jobs: list[ReflectionJob] = []

    def submit(self, job: ReflectionJob) -> None:
        self.jobs.append(job)


class BlockingReflectionService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def reflect(self, **kwargs) -> MemoryReflectionResult:
        self.started.set()
        self.release.wait(timeout=2)
        return MemoryReflectionResult(should_remember=False)


class FakeContextBuilderService:
    def build(self, **kwargs) -> BuiltPromptContext:
        request_id = kwargs["request_id"]
        return BuiltPromptContext(
            prompt="prompt",
            report=ContextReport(
                request_id=request_id,
                token_budget=3000,
                estimated_prompt_tokens=12,
                estimated_saved_tokens=0,
                selected_short_term_messages=0,
                selected_long_term_memories=0,
            ),
            selected_short_term_memory=[],
            selected_long_term_memory=[],
            selected_shared_knowledge=[],
            summary_memory="",
        )


class FakeTraceService:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save_chat_trace(self, **kwargs) -> None:
        self.saved.append(kwargs)


class FakeGameService:
    def get_player_state(self, player_id: str):
        if player_id == PLAYERS[0].player_id:
            return PLAYERS[0]
        return None


class FakeStreamingChatService:
    def stream_chat(self, **kwargs):
        yield 'event: start\ndata: {"request_id":"route-test"}\n\n'
        yield 'event: delta\ndata: {"text":"h"}\n\n'
        yield 'event: final\ndata: {"reply":"h"}\n\n'


class ChatStreamTests(unittest.TestCase):
    def test_chat_service_streams_delta_then_final_and_persists_side_effects(self) -> None:
        service = ChatService.__new__(ChatService)
        service.llm_client = FakeLLMClient()
        service.memory_service = FakeMemoryService()
        service.long_term_memory_service = FakeLongTermMemoryService()
        service.shared_knowledge_service = None
        service.tool_service = FakeToolService()
        service.reflection_service = FakeReflectionService()
        service.reflection_worker = FakeReflectionWorker()
        service.context_builder_service = FakeContextBuilderService()
        service.trace_service = FakeTraceService()

        raw_events = "".join(
            service.stream_chat(
                npc=NPCS[0],
                player_state=PLAYERS[0],
                message="hi",
            )
        )
        events = parse_sse_events(raw_events)

        self.assertEqual(events[0][0], "start")
        self.assertEqual([event for event, _ in events[1:6]], ["delta"] * 5)
        self.assertEqual("".join(data["text"] for _, data in events[1:6]), "hello")
        self.assertEqual(events[-1][0], "final")
        self.assertEqual(events[-1][1]["reply"], "hello")
        self.assertEqual(events[-1][1]["context_report"]["request_id"], events[0][1]["request_id"])

        self.assertEqual(
            [(message.role, message.content) for message in service.memory_service.messages],
            [("player", "hi"), ("npc", "hello")],
        )
        self.assertEqual(len(service.trace_service.saved), 1)
        self.assertEqual(service.trace_service.saved[0]["reply"], "hello")
        self.assertEqual(len(service.reflection_worker.jobs), 1)
        self.assertEqual(service.reflection_worker.jobs[0].player_message, "hi")

    def test_chat_returns_before_background_reflection_finishes(self) -> None:
        blocking_reflection = BlockingReflectionService()
        reflection_worker = ReflectionWorker(
            reflection_service=blocking_reflection,
            long_term_memory_service=FakeLongTermMemoryService(),
            mode="background",
            shutdown_timeout_seconds=1,
        )
        service = ChatService.__new__(ChatService)
        service.llm_client = FakeLLMClient()
        service.memory_service = FakeMemoryService()
        service.long_term_memory_service = FakeLongTermMemoryService()
        service.shared_knowledge_service = None
        service.tool_service = FakeToolService()
        service.reflection_service = blocking_reflection
        service.reflection_worker = reflection_worker
        service.context_builder_service = FakeContextBuilderService()
        service.trace_service = FakeTraceService()

        started_at = time.perf_counter()
        try:
            response = service.chat(
                npc=NPCS[0],
                player_state=PLAYERS[0],
                message="hi",
            )
            elapsed_seconds = time.perf_counter() - started_at

            self.assertEqual(response.reply, "hello")
            self.assertLess(elapsed_seconds, 0.5)
            self.assertTrue(blocking_reflection.started.wait(timeout=0.5))
        finally:
            blocking_reflection.release.set()
            reflection_worker.close()

    def test_stream_chat_route_returns_sse_response(self) -> None:
        client = TestClient(app)

        with patch.object(
            chat_api,
            "game_service",
            FakeGameService(),
        ), patch.object(
            chat_api,
            "chat_service",
            FakeStreamingChatService(),
        ):
            response = client.post(
                f"/chat/{NPCS[0].npc_id}/stream",
                json={
                    "player_id": PLAYERS[0].player_id,
                    "message": "hi",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])

        events = parse_sse_events(response.text)
        self.assertEqual([event for event, _ in events], ["start", "delta", "final"])
        self.assertEqual(events[1][1]["text"], "h")


if __name__ == "__main__":
    unittest.main()
