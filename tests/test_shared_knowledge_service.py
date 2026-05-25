import unittest
import uuid
from pathlib import Path

from app.repositories.shared_knowledge_repository import SharedKnowledgeRepository
from app.services.shared_knowledge_service import SharedKnowledgeService


class SharedKnowledgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"shared_knowledge_{uuid.uuid4().hex}.db"
        repository = SharedKnowledgeRepository(db_path=str(self.db_path))
        self.service = SharedKnowledgeService(repository=repository)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_relevant_events_are_visible_to_known_npc_and_player_scoped(self) -> None:
        event = self.service.publish_event(
            text="The tavern keeper is looking for Gary.",
            player_id="player_001",
            source_npc_id="tavernkeeper_001",
            subject_npc_ids=["tavernkeeper_001"],
            known_by_npc_ids=["blacksmith_001"],
            event_type="request",
        )

        blacksmith_events = self.service.get_relevant_events(
            player_id="player_001",
            npc_id="blacksmith_001",
            query="tavern",
        )
        tavernkeeper_events = self.service.get_relevant_events(
            player_id="player_001",
            npc_id="tavernkeeper_001",
            query="looking",
        )
        other_player_events = self.service.get_relevant_events(
            player_id="player_002",
            npc_id="blacksmith_001",
            query="tavern",
        )
        unrelated_npc_events = self.service.get_relevant_events(
            player_id="player_001",
            npc_id="guard_001",
            query="tavern",
        )

        self.assertEqual([item.event_id for item in blacksmith_events], [event.event_id])
        self.assertEqual([item.event_id for item in tavernkeeper_events], [event.event_id])
        self.assertEqual(other_player_events, [])
        self.assertEqual(unrelated_npc_events, [])

    def test_resolved_events_are_not_returned_as_active_context(self) -> None:
        event = self.service.publish_event(
            text="The tavern keeper is looking for Gary.",
            player_id="player_001",
            source_npc_id="tavernkeeper_001",
            known_by_npc_ids=["blacksmith_001"],
        )

        self.service.resolve_event(event.event_id)

        active_events = self.service.get_relevant_events(
            player_id="player_001",
            npc_id="blacksmith_001",
            query="tavern",
        )
        all_events = self.service.list_events(
            player_id="player_001",
            npc_id="blacksmith_001",
            status=None,
        )

        self.assertEqual(active_events, [])
        self.assertEqual(len(all_events), 1)
        self.assertEqual(all_events[0].status, "resolved")


if __name__ == "__main__":
    unittest.main()
