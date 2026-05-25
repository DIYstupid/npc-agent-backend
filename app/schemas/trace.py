from pydantic import BaseModel, Field

from app.schemas.chat import AgentAction, ChatMessage
from app.schemas.context import ContextReport
from app.schemas.memory import LongTermMemory
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.tool import ToolExecutionResult


class PromptTraceSummary(BaseModel):
    request_id: str
    created_at: str
    agent_type: str = "chat"
    npc_id: str
    player_id: str
    message_preview: str
    estimated_prompt_tokens: int
    estimated_saved_tokens: int
    actions_count: int
    executed_actions_count: int
    elapsed_ms: int
    error: str | None = None


class PromptTraceRecord(BaseModel):
    request_id: str
    created_at: str
    agent_type: str = "chat"
    npc_id: str
    player_id: str
    message: str
    reply: str
    prompt: str
    context_report: ContextReport
    actions: list[AgentAction] = Field(default_factory=list)
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)
    selected_short_term_memory: list[ChatMessage] = Field(default_factory=list)
    selected_long_term_memory: list[LongTermMemory] = Field(default_factory=list)
    selected_shared_knowledge: list[KnowledgeEvent] = Field(default_factory=list)
    summary_memory: str = ""
    agent_state: dict = Field(default_factory=dict)
    elapsed_ms: int = 0
    error: str | None = None


class PromptTraceListResponse(BaseModel):
    traces: list[PromptTraceSummary]
