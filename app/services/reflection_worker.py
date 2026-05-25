import logging
import queue
import threading
from dataclasses import dataclass

from app.schemas.chat import AgentAction
from app.schemas.game import PlayerState
from app.schemas.npc import NPCProfile
from app.schemas.tool import ToolExecutionResult
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.reflection_service import ReflectionService


logger = logging.getLogger(__name__)


REFLECTION_MODE_BACKGROUND = "background"
REFLECTION_MODE_SYNC = "sync"
REFLECTION_MODE_OFF = "off"
VALID_REFLECTION_MODES = {
    REFLECTION_MODE_BACKGROUND,
    REFLECTION_MODE_SYNC,
    REFLECTION_MODE_OFF,
}


@dataclass(frozen=True)
class ReflectionJob:
    request_id: str
    npc: NPCProfile
    player_state: PlayerState
    player_message: str
    npc_reply: str
    actions: list[AgentAction]
    executed_actions: list[ToolExecutionResult]


class ReflectionWorker:
    """Runs memory reflection outside the user-visible chat path."""

    def __init__(
        self,
        reflection_service: ReflectionService,
        long_term_memory_service: LongTermMemoryService,
        mode: str = REFLECTION_MODE_BACKGROUND,
        shutdown_timeout_seconds: float = 5.0,
    ) -> None:
        normalized_mode = mode.lower().strip()
        if normalized_mode not in VALID_REFLECTION_MODES:
            logger.warning(
                "reflection.invalid_mode mode=%s fallback=%s",
                mode,
                REFLECTION_MODE_BACKGROUND,
            )
            normalized_mode = REFLECTION_MODE_BACKGROUND

        self.reflection_service = reflection_service
        self.long_term_memory_service = long_term_memory_service
        self.mode = normalized_mode
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self._queue: queue.Queue[ReflectionJob | None] = queue.Queue()
        self._closed = False
        self._thread: threading.Thread | None = None

        if self.mode == REFLECTION_MODE_BACKGROUND:
            self._thread = threading.Thread(
                target=self._run,
                name="reflection-worker",
                daemon=True,
            )
            self._thread.start()

    def submit(self, job: ReflectionJob) -> None:
        if self.mode == REFLECTION_MODE_OFF:
            logger.debug(
                "reflection.skipped request_id=%s reason=mode_off",
                job.request_id,
            )
            return

        if self.mode == REFLECTION_MODE_SYNC:
            self._process_job(job)
            return

        if self._closed:
            logger.warning(
                "reflection.submit_after_close request_id=%s npc_id=%s player_id=%s",
                job.request_id,
                job.npc.npc_id,
                job.player_state.player_id,
            )
            return

        self._queue.put(job)

    def close(self) -> None:
        if self.mode != REFLECTION_MODE_BACKGROUND or self._thread is None:
            return

        if self._closed:
            return

        self._closed = True
        self._queue.put(None)
        self._thread.join(timeout=self.shutdown_timeout_seconds)
        if self._thread.is_alive():
            logger.warning(
                "reflection.worker_shutdown_timeout timeout_seconds=%s",
                self.shutdown_timeout_seconds,
            )

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return

                self._process_job(job)
            finally:
                self._queue.task_done()

    def _process_job(self, job: ReflectionJob) -> None:
        try:
            reflection_result = self.reflection_service.reflect(
                npc=job.npc,
                player_state=job.player_state,
                player_message=job.player_message,
                npc_reply=job.npc_reply,
                actions=job.actions,
                executed_actions=job.executed_actions,
            )

            if not reflection_result.should_remember or not reflection_result.memory_text:
                logger.debug(
                    "reflection.not_remembered request_id=%s npc_id=%s player_id=%s",
                    job.request_id,
                    job.npc.npc_id,
                    job.player_state.player_id,
                )
                return

            existing_memories = self.long_term_memory_service.search_memory(
                npc_id=job.npc.npc_id,
                player_id=job.player_state.player_id,
                query=reflection_result.memory_text,
                top_k=1,
            )

            for memory in existing_memories:
                if memory.text == reflection_result.memory_text:
                    logger.debug(
                        "reflection.duplicate_memory request_id=%s memory_id=%s",
                        job.request_id,
                        memory.memory_id,
                    )
                    return

            memory = self.long_term_memory_service.add_memory(
                npc_id=job.npc.npc_id,
                player_id=job.player_state.player_id,
                text=reflection_result.memory_text,
                memory_type=reflection_result.memory_type,
                importance=reflection_result.importance,
                tags=["reflection"],
            )
            logger.info(
                "reflection.memory_saved request_id=%s memory_id=%s npc_id=%s player_id=%s",
                job.request_id,
                memory.memory_id,
                job.npc.npc_id,
                job.player_state.player_id,
            )
        except Exception:
            logger.exception(
                "reflection.job_failed request_id=%s npc_id=%s player_id=%s",
                job.request_id,
                job.npc.npc_id,
                job.player_state.player_id,
            )
