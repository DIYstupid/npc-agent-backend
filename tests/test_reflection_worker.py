import unittest
import uuid

from app.data.seed import NPCS, PLAYERS
from app.schemas.memory import LongTermMemory
from app.schemas.reflection import MemoryReflectionResult
from app.services.reflection_worker import ReflectionJob, ReflectionWorker


class StaticReflectionService:
    def __init__(self) -> None:
        self.calls = 0

    def reflect(self, **kwargs) -> MemoryReflectionResult:
        self.calls += 1
        return MemoryReflectionResult(
            should_remember=True,
            memory_text="player promised to bring ore",
            memory_type="quest",
            importance=4,
        )


class FakeLongTermMemoryService:
    def __init__(self) -> None:
        self.memories: list[LongTermMemory] = []

    def search_memory(self, **kwargs) -> list[LongTermMemory]:
        query = kwargs["query"]
        return [memory for memory in self.memories if memory.text == query]

    def add_memory(
        self,
        npc_id: str,
        player_id: str,
        text: str,
        memory_type: str,
        importance: int,
        tags: list[str],
    ) -> LongTermMemory:
        memory = LongTermMemory(
            memory_id=str(uuid.uuid4()),
            npc_id=npc_id,
            player_id=player_id,
            text=text,
            memory_type=memory_type,
            importance=importance,
            tags=list(tags),
            created_at="2026-05-09T00:00:00Z",
        )
        self.memories.append(memory)
        return memory


def make_job() -> ReflectionJob:
    return ReflectionJob(
        request_id="reflection-test",
        npc=NPCS[0],
        player_state=PLAYERS[0],
        player_message="hi",
        npc_reply="hello",
        actions=[],
        executed_actions=[],
    )


class ReflectionWorkerTests(unittest.TestCase):
    def test_sync_mode_writes_memory_and_skips_duplicate_text(self) -> None:
        reflection_service = StaticReflectionService()
        long_term_memory_service = FakeLongTermMemoryService()
        worker = ReflectionWorker(
            reflection_service=reflection_service,
            long_term_memory_service=long_term_memory_service,
            mode="sync",
        )

        worker.submit(make_job())
        worker.submit(make_job())

        self.assertEqual(reflection_service.calls, 2)
        self.assertEqual(len(long_term_memory_service.memories), 1)
        memory = long_term_memory_service.memories[0]
        self.assertEqual(memory.text, "player promised to bring ore")
        self.assertEqual(memory.memory_type, "quest")
        self.assertEqual(memory.tags, ["reflection"])

    def test_off_mode_skips_reflection(self) -> None:
        reflection_service = StaticReflectionService()
        long_term_memory_service = FakeLongTermMemoryService()
        worker = ReflectionWorker(
            reflection_service=reflection_service,
            long_term_memory_service=long_term_memory_service,
            mode="off",
        )

        worker.submit(make_job())

        self.assertEqual(reflection_service.calls, 0)
        self.assertEqual(long_term_memory_service.memories, [])


if __name__ == "__main__":
    unittest.main()
