import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """
    项目配置。
    """

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL",
        "https://api.openai.com/v1",
    )
    LLM_MODEL: str = os.getenv(
        "LLM_MODEL",
        "gpt-4.1-mini",
    )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    SHORT_TERM_MEMORY_MAX_MESSAGES: int = int(
        os.getenv("SHORT_TERM_MEMORY_MAX_MESSAGES", "10")
    )

    # Chroma / Long-term memory
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        "app/data/chroma",
    )
    LONG_TERM_MEMORY_COLLECTION: str = os.getenv(
        "LONG_TERM_MEMORY_COLLECTION",
        "npc_long_term_memory",
    )
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    EMBEDDING_LOCAL_FILES_ONLY: bool = os.getenv(
        "EMBEDDING_LOCAL_FILES_ONLY",
        "true",
    ).lower() in {"1", "true", "yes", "on"}
    LONG_TERM_MEMORY_TOP_K: int = int(
        os.getenv("LONG_TERM_MEMORY_TOP_K", "3")
    )

    # Prompt context budget
    PROMPT_TOKEN_BUDGET: int = int(os.getenv("PROMPT_TOKEN_BUDGET", "3000"))
    SHORT_TERM_MEMORY_TOKEN_BUDGET: int = int(
        os.getenv("SHORT_TERM_MEMORY_TOKEN_BUDGET", "600")
    )
    SUMMARY_MEMORY_TOKEN_BUDGET: int = int(
        os.getenv("SUMMARY_MEMORY_TOKEN_BUDGET", "350")
    )
    LONG_TERM_MEMORY_TOKEN_BUDGET: int = int(
        os.getenv("LONG_TERM_MEMORY_TOKEN_BUDGET", "700")
    )
    CONTEXT_LONG_TERM_CANDIDATE_TOP_K: int = int(
        os.getenv("CONTEXT_LONG_TERM_CANDIDATE_TOP_K", "6")
    )

    # RAG knowledge base
    RAG_KNOWLEDGE_COLLECTION: str = os.getenv(
        "RAG_KNOWLEDGE_COLLECTION",
        "npc_rag_knowledge",
    )
    RAG_CHUNK_TOKEN_BUDGET: int = int(
        os.getenv("RAG_CHUNK_TOKEN_BUDGET", "350")
    )
    RAG_CONTEXT_TOKEN_BUDGET: int = int(
        os.getenv("RAG_CONTEXT_TOKEN_BUDGET", "600")
    )
    CONTEXT_RAG_CANDIDATE_TOP_K: int = int(
        os.getenv("CONTEXT_RAG_CANDIDATE_TOP_K", "6")
    )

    # Observability
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TRACE_DB_PATH: str = os.getenv("TRACE_DB_PATH", "app/data/agent_traces.db")
    TRACE_MAX_RECORDS: int = int(os.getenv("TRACE_MAX_RECORDS", "200"))
    LANGGRAPH_CHECKPOINT_DB_PATH: str = os.getenv(
        "LANGGRAPH_CHECKPOINT_DB_PATH",
        "app/data/langgraph_checkpoints.db",
    )

    # Shared knowledge
    SHARED_KNOWLEDGE_DB_PATH: str = os.getenv(
        "SHARED_KNOWLEDGE_DB_PATH",
        "app/data/shared_knowledge.db",
    )
    SHARED_KNOWLEDGE_TOP_K: int = int(os.getenv("SHARED_KNOWLEDGE_TOP_K", "5"))

    # Story import
    STORY_DB_PATH: str = os.getenv("STORY_DB_PATH", "app/data/story.db")

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv(
        "RATE_LIMIT_ENABLED",
        "true",
    ).lower() in {"1", "true", "yes", "on"}
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    )
    RATE_LIMIT_EXCLUDED_PATHS: set[str] = {
        path.strip()
        for path in os.getenv("RATE_LIMIT_EXCLUDED_PATHS", "/health").split(",")
        if path.strip()
    }

    # Reflection
    REFLECTION_MODE: str = os.getenv("REFLECTION_MODE", "background").lower()
    REFLECTION_WORKER_SHUTDOWN_TIMEOUT_SECONDS: float = float(
        os.getenv("REFLECTION_WORKER_SHUTDOWN_TIMEOUT_SECONDS", "5")
    )


settings = Settings()
