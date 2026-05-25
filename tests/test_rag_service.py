import shutil
import unittest
import uuid
from pathlib import Path

from app.services.rag_knowledge_service import RagKnowledgeService
from app.services.token_budget_service import TokenBudgetService


class RagKnowledgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.persist_dir = Path("tests/.tmp") / f"rag_{uuid.uuid4().hex}"
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.service = RagKnowledgeService(
            persist_dir=str(self.persist_dir),
            collection_name=f"rag_test_{uuid.uuid4().hex}",
            embedding_model_name="missing-local-model",
            token_budget_service=TokenBudgetService(),
            chunk_token_budget=40,
        )
        self.service.embedding_model_unavailable = True

    def tearDown(self) -> None:
        self.service.close()
        if self.persist_dir.exists():
            shutil.rmtree(self.persist_dir)

    def test_import_markdown_and_search_chunks(self) -> None:
        response = self.service.import_document(
            doc_id="lore_doc",
            source="docs/lore.md",
            title="Lore",
            document_format="markdown",
            content=(
                "# World Lore\n"
                "The moonwell opens only when the silver bell rings.\n\n"
                "## Village Rules\n"
                "The blacksmith repairs old swords after receiving iron ore."
            ),
            tags=["lore", "quest"],
        )

        self.assertEqual(response.doc_id, "lore_doc")
        self.assertGreaterEqual(len(response.chunks), 1)
        self.assertTrue(
            all(chunk.source == "docs/lore.md" for chunk in response.chunks)
        )

        results = self.service.search(
            query="moonwell silver bell",
            top_k=3,
            keyword="moonwell",
            tags=["lore"],
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].doc_id, "lore_doc")
        self.assertIn("moonwell", results[0].text.lower())
        self.assertIsNotNone(results[0].score)


if __name__ == "__main__":
    unittest.main()
