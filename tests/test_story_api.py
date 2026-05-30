import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import story as story_api
from app.main import app
from app.schemas.rag import RagDocumentChunk
from app.schemas.story import (
    StoryActivationResponse,
    StoryImportPreview,
)
from app.services.story_import_service import StoryMarkdownHeuristicParser, StoryValidationService


class FakeStoryImportService:
    def __init__(self) -> None:
        self.parser = StoryMarkdownHeuristicParser()
        self.validation_service = StoryValidationService()
        self.records: dict[str, dict] = {}
        self.rag_chunks: dict[str, RagDocumentChunk] = {}

    def import_story(
        self,
        content: str,
        source: str,
        title: str | None = None,
        activate: bool = False,
        player_id: str | None = None,
    ) -> StoryImportPreview:
        graph = self.parser.parse(
            content=content,
            source=source,
            title=title,
        )
        validation = self.validation_service.validate(graph)
        rag_doc_id = f"{graph.story_id}_source"
        chunk = RagDocumentChunk(
            chunk_id=f"{rag_doc_id}:0000",
            doc_id=rag_doc_id,
            text=content,
            source=source,
            page=0,
            heading=title,
            created_at="2026-05-30T00:00:00Z",
            tags=[
                "story",
                "world_bible",
                "main_plot",
                f"story_id:{graph.story_id}",
            ],
        )
        self.rag_chunks[rag_doc_id] = chunk
        status = "invalid" if validation.has_errors else "needs_review"
        if not validation.has_errors and not validation.has_warnings:
            status = "valid"
        self.records[graph.story_id] = {
            "story_id": graph.story_id,
            "title": graph.title,
            "source": source,
            "rag_doc_id": rag_doc_id,
            "raw_markdown": content,
            "graph": graph.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
            "status": "draft",
            "created_at": "2026-05-30T00:00:00Z",
            "activated_at": None,
        }
        return StoryImportPreview(
            story_id=graph.story_id,
            rag_doc_id=rag_doc_id,
            candidate_graph=graph,
            validation=validation,
            status=status,
        )

    def get_story(self, story_id: str):
        return self.records.get(story_id)

    def activate_story(
        self,
        story_id: str,
        player_id: str | None = None,
    ) -> StoryActivationResponse | None:
        record = self.records.get(story_id)
        if record is None:
            return None
        record["status"] = "active"
        return StoryActivationResponse(
            story_id=story_id,
            status="active",
            progress=None,
        )


class StoryApiTests(unittest.TestCase):
    def test_import_get_and_activate_story_routes(self) -> None:
        client = TestClient(app)
        fake_service = FakeStoryImportService()

        with patch.object(story_api, "story_import_service", fake_service):
            import_response = client.post(
                "/story/import",
                json={
                    "source": "docs/story.md",
                    "title": "Demo Story",
                    "content": (
                        "# Main Story\n"
                        "- Travel to the training hall\n"
                        "- Defeat bandit captain"
                    ),
                },
            )
            self.assertEqual(import_response.status_code, 200)
            import_payload = import_response.json()
            self.assertEqual(import_payload["status"], "valid")
            self.assertEqual(import_payload["candidate_graph"]["title"], "Demo Story")

            story_id = import_payload["story_id"]
            get_response = client.get(f"/story/{story_id}")
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(get_response.json()["story_id"], story_id)

            activate_response = client.post(
                f"/story/{story_id}/activate",
                json={"player_id": "player_001"},
            )
            self.assertEqual(activate_response.status_code, 200)
            self.assertEqual(activate_response.json()["status"], "active")

        self.assertEqual(
            fake_service.rag_chunks[import_payload["rag_doc_id"]].tags[:3],
            ["story", "world_bible", "main_plot"],
        )

    def test_get_unknown_story_returns_404(self) -> None:
        client = TestClient(app)
        fake_service = FakeStoryImportService()

        with patch.object(story_api, "story_import_service", fake_service):
            response = client.get("/story/missing_story")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
