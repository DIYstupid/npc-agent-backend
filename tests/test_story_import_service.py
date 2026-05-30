import unittest
import uuid
from pathlib import Path

from app.repositories.story_repository import StoryRepository
from app.schemas.rag import RagDocumentChunk, RagDocumentImportResponse
from app.services.story_import_service import StoryActivationError, StoryImportService


class FakeRagKnowledgeService:
    def __init__(self) -> None:
        self.documents: dict[str, RagDocumentChunk] = {}
        self.import_calls: list[dict] = []

    def import_document(self, **kwargs) -> RagDocumentImportResponse:
        self.import_calls.append(kwargs)
        doc_id = kwargs["doc_id"]
        chunk = RagDocumentChunk(
            chunk_id=f"{doc_id}:0000",
            doc_id=doc_id,
            text=kwargs["content"],
            source=kwargs["source"],
            page=kwargs["page"],
            heading=kwargs["title"],
            created_at="2026-05-30T00:00:00Z",
            tags=list(kwargs["tags"]),
        )
        self.documents[doc_id] = chunk
        return RagDocumentImportResponse(
            doc_id=doc_id,
            source=kwargs["source"],
            chunks=[chunk],
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: str | None = None,
        source: str | None = None,
        keyword: str | None = None,
        tags: list[str] | None = None,
    ) -> list[RagDocumentChunk]:
        normalized_query = query.lower()
        normalized_tags = set(tags or [])
        chunks = list(self.documents.values())
        if doc_id:
            chunks = [chunk for chunk in chunks if chunk.doc_id == doc_id]
        if source:
            chunks = [chunk for chunk in chunks if chunk.source == source]
        return [
            chunk.model_copy(update={"score": 1.0})
            for chunk in chunks
            if normalized_query in chunk.text.lower()
            and normalized_tags.issubset(set(chunk.tags))
        ][:top_k]


class StoryImportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"story_{uuid.uuid4().hex}.db"
        self.rag_service = FakeRagKnowledgeService()
        self.repository = StoryRepository(db_path=str(self.db_path))
        self.service = StoryImportService(
            repository=self.repository,
            rag_knowledge_service=self.rag_service,
        )

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_loose_markdown_import_saves_preview_and_rag_document(self) -> None:
        preview = self.service.import_story(
            source="docs/wuxia_story.md",
            title="Wuxia Story",
            content=(
                "# World\n"
                "Qingyun Sect watches the mountain road.\n\n"
                "# Main Story\n"
                "The protagonist starts in village square, "
                "defeats local bandits, "
                "joins Qingyun Sect, "
                "and finally defeats Blackwater Fort boss."
            ),
        )

        self.assertEqual(preview.status, "needs_review")
        self.assertEqual(preview.candidate_graph.title, "Wuxia Story")
        self.assertGreaterEqual(len(preview.candidate_graph.stages), 3)
        self.assertEqual(
            self.rag_service.import_calls[0]["tags"],
            [
                "story",
                "world_bible",
                "main_plot",
                f"story_id:{preview.story_id}",
            ],
        )

        stored = self.repository.get_story(preview.story_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.rag_doc_id, preview.rag_doc_id)

        chunks = self.rag_service.search(
            query="Blackwater",
            tags=["story", "main_plot"],
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].doc_id, preview.rag_doc_id)

    def test_invalid_graph_is_not_activated(self) -> None:
        preview = self.service.import_story(
            source="docs/empty_story.md",
            title="Empty Story",
            content="# World\nOnly lore is written here.",
            activate=True,
            player_id="player_001",
        )

        self.assertEqual(preview.status, "invalid")
        stored = self.repository.get_story(preview.story_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "draft")
        self.assertIsNone(
            self.repository.get_player_progress(
                story_id=preview.story_id,
                player_id="player_001",
            )
        )

        with self.assertRaises(StoryActivationError):
            self.service.activate_story(
                story_id=preview.story_id,
                player_id="player_001",
            )

    def test_valid_story_activates_for_player(self) -> None:
        preview = self.service.import_story(
            source="docs/valid_story.md",
            title="Valid Story",
            content=(
                "# Main Story\n"
                "- Travel to the training hall\n"
                "- Defeat bandit captain"
            ),
        )

        response = self.service.activate_story(
            story_id=preview.story_id,
            player_id="player_001",
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.status, "active")
        self.assertIsNotNone(response.progress)
        self.assertEqual(response.progress.player_id, "player_001")
        self.assertEqual(response.progress.current_stage_id, "stage_001")


if __name__ == "__main__":
    unittest.main()
