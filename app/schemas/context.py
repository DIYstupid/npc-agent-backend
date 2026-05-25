from pydantic import BaseModel, Field


class ContextReport(BaseModel):
    """Diagnostics for prompt construction and context budgeting."""

    request_id: str
    token_budget: int
    estimated_prompt_tokens: int
    estimated_saved_tokens: int = 0
    section_tokens: dict[str, int] = Field(default_factory=dict)
    selected_short_term_messages: int = 0
    trimmed_short_term_messages: int = 0
    selected_long_term_memories: int = 0
    trimmed_long_term_memories: int = 0
    selected_shared_knowledge_events: int = 0
    trimmed_shared_knowledge_events: int = 0
    has_summary_memory: bool = False
