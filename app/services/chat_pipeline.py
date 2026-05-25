import logging
import time
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.core.llm import BaseLLMClient
from app.schemas.chat import AgentAction, ChatResponse
from app.schemas.game import PlayerState
from app.schemas.llm import LLMChatResult
from app.schemas.npc import NPCProfile
from app.schemas.rag import RagCitation, RagDocumentChunk
from app.schemas.tool import ToolExecutionBatch, ToolExecutionResult
from app.services.context_builder_service import (
    BuiltPromptContext,
    ContextBuilderService,
)
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_service import MemoryService
from app.services.reflection_worker import ReflectionJob, ReflectionWorker
from app.services.rag_knowledge_service import RagKnowledgeService
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


logger = logging.getLogger(__name__)


@dataclass
class ChatPipelineRun:
    request_id: str
    started_at: float
    npc: NPCProfile
    player_state: PlayerState
    message: str
    built_context: BuiltPromptContext


@dataclass
class ChatPipelineGeneration:
    llm_result: LLMChatResult
    error_text: str | None = None


@dataclass
class ChatPipelineResult:
    run: ChatPipelineRun
    generation: ChatPipelineGeneration
    response: ChatResponse


class ChatPipeline:
    """Executes the chat domain pipeline behind sync and SSE transports."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        memory_service: MemoryService,
        long_term_memory_service: LongTermMemoryService,
        rag_knowledge_service: RagKnowledgeService | None,
        shared_knowledge_service: SharedKnowledgeService | None,
        tool_service: ToolService,
        reflection_worker: ReflectionWorker | None,
        context_builder_service: ContextBuilderService,
        trace_service: TraceService,
    ) -> None:
        self.llm_client = llm_client
        self.memory_service = memory_service
        self.long_term_memory_service = long_term_memory_service
        self.rag_knowledge_service = rag_knowledge_service
        self.shared_knowledge_service = shared_knowledge_service
        self.tool_service = tool_service
        self.reflection_worker = reflection_worker
        self.context_builder_service = context_builder_service
        self.trace_service = trace_service

    def run(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        message: str,
    ) -> ChatPipelineResult:
        pipeline_run = self.start(
            npc=npc,
            player_state=player_state,
            message=message,
        )
        generation = self.generate(pipeline_run)
        response = self.finalize(
            pipeline_run=pipeline_run,
            generation=generation,
        )

        return ChatPipelineResult(
            run=pipeline_run,
            generation=generation,
            response=response,
        )

    def start(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        message: str,
        request_id: str | None = None,
    ) -> ChatPipelineRun:
        request_id = request_id or str(uuid.uuid4())
        started_at = time.perf_counter()

        short_term_memory = self.memory_service.get_messages(
            player_id=player_state.player_id,
            npc_id=npc.npc_id,
        )
        summary_memory = self._get_summary_memory(
            player_id=player_state.player_id,
            npc_id=npc.npc_id,
        )
        long_term_memory = self.long_term_memory_service.search_memory(
            npc_id=npc.npc_id,
            player_id=player_state.player_id,
            query=message,
            top_k=settings.CONTEXT_LONG_TERM_CANDIDATE_TOP_K,
        )
        shared_knowledge = self._get_shared_knowledge(
            npc=npc,
            player_state=player_state,
            message=message,
        )
        rag_chunks = self._get_rag_chunks(message)

        built_context = self.context_builder_service.build(
            request_id=request_id,
            npc=npc,
            player_state=player_state,
            player_message=message,
            short_term_memory=short_term_memory,
            summary_memory=summary_memory,
            long_term_memory=long_term_memory,
            shared_knowledge=shared_knowledge,
            rag_chunks=rag_chunks,
        )
        self._log_context_built(
            request_id=request_id,
            npc=npc,
            player_state=player_state,
            built_context=built_context,
        )

        return ChatPipelineRun(
            request_id=request_id,
            started_at=started_at,
            npc=npc,
            player_state=player_state,
            message=message,
            built_context=built_context,
        )

    def generate(self, pipeline_run: ChatPipelineRun) -> ChatPipelineGeneration:
        try:
            llm_result = self.llm_client.generate(pipeline_run.built_context.prompt)
            return ChatPipelineGeneration(llm_result=llm_result)
        except Exception as exc:
            logger.exception(
                "chat.llm_failed request_id=%s npc_id=%s player_id=%s",
                pipeline_run.request_id,
                pipeline_run.npc.npc_id,
                pipeline_run.player_state.player_id,
            )
            return ChatPipelineGeneration(
                llm_result=LLMChatResult(
                    reply="I lost my train of thought for a moment. Could you say that again?",
                    actions=[],
                ),
                error_text=str(exc),
            )

    def finalize(
        self,
        pipeline_run: ChatPipelineRun,
        generation: ChatPipelineGeneration,
    ) -> ChatResponse:
        reply = generation.llm_result.reply
        actions = generation.llm_result.actions
        action_execution = self._execute_actions(
            player_state=pipeline_run.player_state,
            actions=actions,
        )
        executed_actions = action_execution.executed_actions

        self._write_short_term_memory(
            pipeline_run=pipeline_run,
            reply=reply,
        )
        self._submit_reflection_memory(
            pipeline_run=pipeline_run,
            reply=reply,
            actions=actions,
            executed_actions=executed_actions,
        )
        self._save_trace(
            pipeline_run=pipeline_run,
            reply=reply,
            actions=actions,
            validated_actions=action_execution.validated_actions,
            executed_actions=executed_actions,
            error=generation.error_text,
        )
        self._log_completed(
            pipeline_run=pipeline_run,
            actions=actions,
            executed_actions=executed_actions,
        )

        return ChatResponse(
            npc_id=pipeline_run.npc.npc_id,
            player_id=pipeline_run.player_state.player_id,
            reply=reply,
            actions=actions,
            executed_actions=executed_actions,
            context_report=pipeline_run.built_context.report,
            citations=self._build_citations(
                pipeline_run.built_context.selected_rag_chunks,
            ),
        )

    def _execute_actions(
        self,
        player_state: PlayerState,
        actions: list[AgentAction],
    ) -> ToolExecutionBatch:
        execute_with_validation = getattr(
            self.tool_service,
            "execute_actions_with_validation",
            None,
        )
        if execute_with_validation is not None:
            return execute_with_validation(
                player_id=player_state.player_id,
                actions=actions,
            )

        executed_actions = self.tool_service.execute_actions(
            player_id=player_state.player_id,
            actions=actions,
        )
        return ToolExecutionBatch(
            raw_actions=list(actions),
            validated_actions=list(actions),
            executed_actions=executed_actions,
        )

    def _write_short_term_memory(
        self,
        pipeline_run: ChatPipelineRun,
        reply: str,
    ) -> None:
        self.memory_service.add_message(
            player_id=pipeline_run.player_state.player_id,
            npc_id=pipeline_run.npc.npc_id,
            role="player",
            content=pipeline_run.message,
        )
        self.memory_service.add_message(
            player_id=pipeline_run.player_state.player_id,
            npc_id=pipeline_run.npc.npc_id,
            role="npc",
            content=reply,
        )

    def _submit_reflection_memory(
        self,
        pipeline_run: ChatPipelineRun,
        reply: str,
        actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
    ) -> None:
        if self.reflection_worker is None:
            return

        try:
            self.reflection_worker.submit(
                ReflectionJob(
                    request_id=pipeline_run.request_id,
                    npc=pipeline_run.npc,
                    player_state=pipeline_run.player_state,
                    player_message=pipeline_run.message,
                    npc_reply=reply,
                    actions=actions,
                    executed_actions=executed_actions,
                )
            )
        except Exception:
            logger.exception(
                "chat.reflection_submit_failed request_id=%s npc_id=%s player_id=%s",
                pipeline_run.request_id,
                pipeline_run.npc.npc_id,
                pipeline_run.player_state.player_id,
            )

    def _get_summary_memory(self, player_id: str, npc_id: str) -> str:
        get_summary = getattr(self.memory_service, "get_summary", None)
        if get_summary is None:
            return ""

        return get_summary(
            player_id=player_id,
            npc_id=npc_id,
        )

    def _save_trace(
        self,
        pipeline_run: ChatPipelineRun,
        reply: str,
        actions: list[AgentAction],
        validated_actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
        error: str | None,
    ) -> None:
        elapsed_ms = self._elapsed_ms(pipeline_run)
        try:
            self.trace_service.save_chat_trace(
                request_id=pipeline_run.request_id,
                npc_id=pipeline_run.npc.npc_id,
                player_id=pipeline_run.player_state.player_id,
                message=pipeline_run.message,
                reply=reply,
                prompt=pipeline_run.built_context.prompt,
                context_report=pipeline_run.built_context.report,
                actions=actions,
                validated_actions=validated_actions,
                executed_actions=executed_actions,
                selected_short_term_memory=pipeline_run.built_context.selected_short_term_memory,
                selected_long_term_memory=pipeline_run.built_context.selected_long_term_memory,
                selected_rag_chunks=pipeline_run.built_context.selected_rag_chunks,
                selected_shared_knowledge=pipeline_run.built_context.selected_shared_knowledge,
                summary_memory=pipeline_run.built_context.summary_memory,
                elapsed_ms=elapsed_ms,
                error=error,
            )
        except Exception:
            logger.exception(
                "chat.trace_save_failed request_id=%s npc_id=%s player_id=%s",
                pipeline_run.request_id,
                pipeline_run.npc.npc_id,
                pipeline_run.player_state.player_id,
            )

    def _log_context_built(
        self,
        request_id: str,
        npc: NPCProfile,
        player_state: PlayerState,
        built_context: BuiltPromptContext,
    ) -> None:
        logger.info(
            "chat.context_built request_id=%s npc_id=%s player_id=%s "
            "prompt_tokens=%s saved_tokens=%s short_selected=%s short_trimmed=%s "
            "long_selected=%s long_trimmed=%s rag_selected=%s rag_trimmed=%s "
            "has_summary=%s",
            request_id,
            npc.npc_id,
            player_state.player_id,
            built_context.report.estimated_prompt_tokens,
            built_context.report.estimated_saved_tokens,
            built_context.report.selected_short_term_messages,
            built_context.report.trimmed_short_term_messages,
            built_context.report.selected_long_term_memories,
            built_context.report.trimmed_long_term_memories,
            built_context.report.selected_rag_chunks,
            built_context.report.trimmed_rag_chunks,
            built_context.report.has_summary_memory,
        )

    def _log_completed(
        self,
        pipeline_run: ChatPipelineRun,
        actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
    ) -> None:
        logger.info(
            "chat.completed request_id=%s npc_id=%s player_id=%s "
            "actions=%s executed_actions=%s elapsed_ms=%s",
            pipeline_run.request_id,
            pipeline_run.npc.npc_id,
            pipeline_run.player_state.player_id,
            len(actions),
            len(executed_actions),
            self._elapsed_ms(pipeline_run),
        )

    def _elapsed_ms(self, pipeline_run: ChatPipelineRun) -> int:
        return int((time.perf_counter() - pipeline_run.started_at) * 1000)

    def _get_shared_knowledge(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        message: str,
    ) -> list:
        if self.shared_knowledge_service is None:
            return []

        return self.shared_knowledge_service.get_relevant_events(
            player_id=player_state.player_id,
            npc_id=npc.npc_id,
            query=message,
            top_k=settings.SHARED_KNOWLEDGE_TOP_K,
        )

    def _get_rag_chunks(self, message: str) -> list[RagDocumentChunk]:
        if self.rag_knowledge_service is None:
            return []

        try:
            return self.rag_knowledge_service.search(
                query=message,
                top_k=settings.CONTEXT_RAG_CANDIDATE_TOP_K,
            )
        except Exception:
            logger.exception("chat.rag_search_failed")
            return []

    def _build_citations(
        self,
        chunks: list[RagDocumentChunk],
    ) -> list[RagCitation]:
        return [
            RagCitation(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source=chunk.source,
                page=chunk.page,
                heading=chunk.heading,
                score=chunk.score,
            )
            for chunk in chunks
        ]
