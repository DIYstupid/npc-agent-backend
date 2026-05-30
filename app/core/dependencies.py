import logging

from app.agents.quest_agent import QuestAgent
from app.agents.world_agent import WorldAgent
from app.core.config import settings
from app.repositories.player_state_repository import PlayerStateRepository
from app.repositories.shared_knowledge_repository import SharedKnowledgeRepository
from app.repositories.story_repository import StoryRepository
from app.services.chat_service import ChatService
from app.services.context_builder_service import ContextBuilderService
from app.services.game_service import GameService
from app.services.long_term_memory_service import LongTermMemoryService
from app.services.memory_service import MemoryService
from app.services.rag_knowledge_service import RagKnowledgeService
from app.services.redis_memory_service import RedisMemoryService
from app.services.reflection_service import ReflectionService
from app.services.reflection_worker import ReflectionWorker
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.story_import_service import StoryImportService
from app.services.token_budget_service import TokenBudgetService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService
from app.services.world_action_service import WorldActionService


logger = logging.getLogger(__name__)


player_state_repository = PlayerStateRepository()

game_service = GameService(
    player_state_repository=player_state_repository,
)

try:
    memory_service = RedisMemoryService(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        max_messages=settings.SHORT_TERM_MEMORY_MAX_MESSAGES,
    )
    print("Using RedisMemoryService")
except Exception as exc:
    print(f"Redis unavailable, fallback to MemoryService: {exc}")
    memory_service = MemoryService(
        max_messages=settings.SHORT_TERM_MEMORY_MAX_MESSAGES,
    )


long_term_memory_service = LongTermMemoryService(
    persist_dir=settings.CHROMA_PERSIST_DIR,
    collection_name=settings.LONG_TERM_MEMORY_COLLECTION,
    embedding_model_name=settings.EMBEDDING_MODEL,
)

shared_knowledge_repository = SharedKnowledgeRepository(
    db_path=settings.SHARED_KNOWLEDGE_DB_PATH,
)

shared_knowledge_service = SharedKnowledgeService(
    repository=shared_knowledge_repository,
)

token_budget_service = TokenBudgetService()

rag_knowledge_service = RagKnowledgeService(
    persist_dir=settings.CHROMA_PERSIST_DIR,
    collection_name=settings.RAG_KNOWLEDGE_COLLECTION,
    embedding_model_name=settings.EMBEDDING_MODEL,
    token_budget_service=token_budget_service,
    chunk_token_budget=settings.RAG_CHUNK_TOKEN_BUDGET,
)

story_repository = StoryRepository(
    db_path=settings.STORY_DB_PATH,
)

story_import_service = StoryImportService(
    repository=story_repository,
    rag_knowledge_service=rag_knowledge_service,
)

context_builder_service = ContextBuilderService(
    token_budget_service=token_budget_service,
)

tool_service = ToolService(
    game_service=game_service,
    shared_knowledge_service=shared_knowledge_service,
)

reflection_service = ReflectionService()

reflection_worker = ReflectionWorker(
    reflection_service=reflection_service,
    long_term_memory_service=long_term_memory_service,
    mode=settings.REFLECTION_MODE,
    shutdown_timeout_seconds=settings.REFLECTION_WORKER_SHUTDOWN_TIMEOUT_SECONDS,
)

trace_service = TraceService()

quest_agent = QuestAgent(
    tool_service=tool_service,
    game_service=game_service,
    trace_service=trace_service,
    checkpoint_db_path=settings.LANGGRAPH_CHECKPOINT_DB_PATH,
)

world_agent = WorldAgent(
    shared_knowledge_service=shared_knowledge_service,
    tool_service=tool_service,
    trace_service=trace_service,
    checkpoint_db_path=settings.LANGGRAPH_CHECKPOINT_DB_PATH,
)

world_action_service = WorldActionService(
    game_service=game_service,
    tool_service=tool_service,
    world_agent=world_agent,
    trace_service=trace_service,
)
world_agent.set_world_action_service(world_action_service)

chat_service = ChatService(
    memory_service=memory_service,
    long_term_memory_service=long_term_memory_service,
    shared_knowledge_service=shared_knowledge_service,
    tool_service=tool_service,
    reflection_service=reflection_service,
    context_builder_service=context_builder_service,
    trace_service=trace_service,
    reflection_worker=reflection_worker,
    rag_knowledge_service=rag_knowledge_service,
)


def close_resources() -> None:
    resources = [
        chat_service,
        reflection_worker,
        memory_service,
        long_term_memory_service,
        rag_knowledge_service,
        story_repository,
        shared_knowledge_service,
        trace_service,
        quest_agent,
        world_agent,
        world_action_service,
        game_service,
    ]

    for resource in resources:
        close = getattr(resource, "close", None)
        if close is None:
            continue

        try:
            close()
        except Exception:
            logger.exception(
                "resource.close_failed resource=%s",
                resource.__class__.__name__,
            )
