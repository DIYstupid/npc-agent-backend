import unittest

from app.data.seed import NPCS, PLAYERS
from app.schemas.chat import ChatMessage
from app.schemas.memory import LongTermMemory
from app.schemas.rag import RagDocumentChunk
from app.schemas.shared_knowledge import KnowledgeEvent
from app.services.context_builder_service import ContextBuilderService
from app.services.token_budget_service import TokenBudgetService


class ContextBuilderServiceTests(unittest.TestCase):
    def test_context_report_tracks_trimmed_short_term_memory(self) -> None:
        service = ContextBuilderService(TokenBudgetService())
        messages = [
            ChatMessage(
                role="player",
                content=("very long message " * 20) + str(index),
            )
            for index in range(8)
        ]
        memories = [
            LongTermMemory(
                memory_id="memory_001",
                npc_id="blacksmith_001",
                player_id="player_001",
                text="player helped the blacksmith repair a sword",
                importance=5,
            )
        ]

        context = service.build(
            request_id="unit-test",
            npc=NPCS[0],
            player_state=PLAYERS[0],
            player_message="repair sword",
            short_term_memory=messages,
            summary_memory="older conversation summary",
            long_term_memory=memories,
        )

        self.assertTrue(context.prompt)
        self.assertEqual(context.report.request_id, "unit-test")
        self.assertGreater(context.report.estimated_prompt_tokens, 0)
        self.assertGreaterEqual(
            context.report.trimmed_short_term_messages,
            0,
        )
        self.assertIn("full_prompt", context.report.section_tokens)

    def test_context_includes_shared_knowledge(self) -> None:
        service = ContextBuilderService(TokenBudgetService())
        event = KnowledgeEvent(
            event_id="knowledge_001",
            player_id="player_001",
            related_player_ids=["player_001"],
            text="The tavern keeper is looking for Gary.",
            source_npc_id="tavernkeeper_001",
            subject_npc_ids=["tavernkeeper_001"],
            known_by_npc_ids=["blacksmith_001"],
            event_type="request",
        )

        context = service.build(
            request_id="unit-test-knowledge",
            npc=NPCS[0],
            player_state=PLAYERS[0],
            player_message="Any news?",
            short_term_memory=[],
            summary_memory="",
            long_term_memory=[],
            shared_knowledge=[event],
        )

        self.assertIn("The tavern keeper is looking for Gary.", context.prompt)
        self.assertEqual(context.selected_shared_knowledge, [event])
        self.assertEqual(context.report.selected_shared_knowledge_events, 1)
        self.assertIn("shared_knowledge", context.report.section_tokens)

    def test_context_includes_rag_chunks(self) -> None:
        service = ContextBuilderService(TokenBudgetService())
        chunk = RagDocumentChunk(
            chunk_id="project_doc:0001",
            doc_id="project_doc",
            text="The moonwell opens only when the silver bell rings.",
            source="docs/project_lore.md",
            page=2,
            heading="World Lore",
            created_at="2026-05-25T00:00:00Z",
            tags=["lore"],
            score=0.92,
        )

        context = service.build(
            request_id="unit-test-rag",
            npc=NPCS[0],
            player_state=PLAYERS[0],
            player_message="How does the moonwell open?",
            short_term_memory=[],
            summary_memory="",
            long_term_memory=[],
            rag_chunks=[chunk],
        )

        self.assertIn("[Knowledge Base RAG]", context.prompt)
        self.assertIn("moonwell", context.prompt)
        self.assertEqual(context.selected_rag_chunks, [chunk])
        self.assertEqual(context.report.selected_rag_chunks, 1)
        self.assertIn("rag_knowledge", context.report.section_tokens)


if __name__ == "__main__":
    unittest.main()
