import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

from app.core.llm import get_llm_client
from app.schemas.chat import ChatResponse
from app.schemas.game import PlayerState
from app.schemas.npc import NPCProfile
from app.services.chat_pipeline import ChatPipeline
from app.services.context_builder_service import ContextBuilderService
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_service import MemoryService
from app.services.reflection_service import ReflectionService
from app.services.reflection_worker import ReflectionWorker
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


logger = logging.getLogger(__name__)


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(_to_jsonable(data), ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


class ChatService:
    """Transport-facing facade for chat requests."""

    def __init__(
        self,
        memory_service: MemoryService,
        long_term_memory_service: LongTermMemoryService,
        shared_knowledge_service: SharedKnowledgeService | None,
        tool_service: ToolService,
        reflection_service: ReflectionService,
        context_builder_service: ContextBuilderService,
        trace_service: TraceService,
        reflection_worker: ReflectionWorker | None = None,
    ) -> None:
        self.llm_client = get_llm_client()
        self.memory_service = memory_service
        self.long_term_memory_service = long_term_memory_service
        self.shared_knowledge_service = shared_knowledge_service
        self.tool_service = tool_service
        self.reflection_service = reflection_service
        self.reflection_worker = reflection_worker
        self.context_builder_service = context_builder_service
        self.trace_service = trace_service

    def chat(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        message: str,
    ) -> ChatResponse:
        return self._pipeline().run(
            npc=npc,
            player_state=player_state,
            message=message,
        ).response

    def stream_chat(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        message: str,
    ) -> Iterator[str]:
        request_id = str(uuid.uuid4())

        try:
            pipeline = self._pipeline()
            pipeline_run = pipeline.start(
                npc=npc,
                player_state=player_state,
                message=message,
                request_id=request_id,
            )

            yield _sse_event(
                "start",
                {
                    "request_id": request_id,
                    "npc_id": npc.npc_id,
                    "player_id": player_state.player_id,
                },
            )

            generation = pipeline.generate(pipeline_run)
            for character in generation.llm_result.reply:
                yield _sse_event("delta", {"text": character})

            response = pipeline.finalize(
                pipeline_run=pipeline_run,
                generation=generation,
            )
            yield _sse_event("final", _to_jsonable(response))
        except Exception as exc:
            logger.exception(
                "chat.stream_failed request_id=%s npc_id=%s player_id=%s",
                request_id,
                npc.npc_id,
                player_state.player_id,
            )
            yield _sse_event(
                "error",
                {
                    "request_id": request_id,
                    "message": str(exc),
                },
            )

    def _pipeline(self) -> ChatPipeline:
        return ChatPipeline(
            llm_client=self.llm_client,
            memory_service=self.memory_service,
            long_term_memory_service=self.long_term_memory_service,
            shared_knowledge_service=getattr(self, "shared_knowledge_service", None),
            tool_service=self.tool_service,
            reflection_worker=getattr(self, "reflection_worker", None),
            context_builder_service=self.context_builder_service,
            trace_service=self.trace_service,
        )

    def close(self) -> None:
        close_client = getattr(self.llm_client, "close", None)
        if close_client is not None:
            close_client()
