import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import rag as rag_api
from app.main import app
from app.schemas.rag import RagDocumentChunk, RagDocumentImportResponse


class FakeRagKnowledgeService:
    def __init__(self) -> None:
        self.chunks: list[RagDocumentChunk] = []

    def import_document(self, **kwargs) -> RagDocumentImportResponse:
        chunk = RagDocumentChunk(
            chunk_id=f"{kwargs['doc_id']}:0000",
            doc_id=kwargs["doc_id"],
            text=kwargs["content"],
            source=kwargs["source"],
            page=kwargs["page"],
            heading=kwargs["title"],
            created_at="2026-05-25T00:00:00Z",
            tags=list(kwargs["tags"]),
            score=None,
        )
        self.chunks = [chunk]
        return RagDocumentImportResponse(
            doc_id=kwargs["doc_id"],
            source=kwargs["source"],
            chunks=self.chunks,
        )

    def search(self, **kwargs) -> list[RagDocumentChunk]:
        query = kwargs["query"].lower()
        return [
            chunk.model_copy(update={"score": 1.0})
            for chunk in self.chunks
            if query in chunk.text.lower()
        ][: kwargs["top_k"]]


class RagApiTests(unittest.TestCase):
    def test_import_and_search_routes(self) -> None:
        client = TestClient(app)
        fake_service = FakeRagKnowledgeService()

        with patch.object(rag_api, "rag_knowledge_service", fake_service):
            import_response = client.post(
                "/rag/documents",
                json={
                    "doc_id": "demo_doc",
                    "source": "docs/demo.md",
                    "title": "Demo",
                    "document_format": "markdown",
                    "content": "# Demo\nThe moonwell opens at midnight.",
                    "tags": ["demo"],
                },
            )
            self.assertEqual(import_response.status_code, 200)
            self.assertEqual(import_response.json()["doc_id"], "demo_doc")
            self.assertEqual(len(import_response.json()["chunks"]), 1)

            search_response = client.get(
                "/rag/search",
                params={
                    "query": "moonwell",
                    "top_k": 3,
                },
            )
            self.assertEqual(search_response.status_code, 200)
            payload = search_response.json()
            self.assertEqual(payload["query"], "moonwell")
            self.assertEqual(payload["chunks"][0]["source"], "docs/demo.md")


if __name__ == "__main__":
    unittest.main()
