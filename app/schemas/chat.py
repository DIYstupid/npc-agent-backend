from pydantic import BaseModel, Field

from app.schemas.context import ContextReport
from app.schemas.rag import RagCitation
from app.schemas.tool import AgentAction, ToolExecutionResult
from app.schemas.validation import ChatText, ResourceId


class ChatRequest(BaseModel):
    """Player chat request."""

    player_id: ResourceId = Field(..., description="Player ID")
    message: ChatText = Field(..., description="Player input")


class ChatMessage(BaseModel):
    """Short-term chat message."""

    role: str = Field(..., description="Message role, such as player or npc")
    content: str = Field(..., description="Message content")


class ChatResponse(BaseModel):
    """NPC chat response."""

    npc_id: ResourceId
    player_id: ResourceId
    reply: str
    actions: list[AgentAction] = Field(default_factory=list)
    executed_actions: list[ToolExecutionResult] = Field(
        default_factory=list,
    )
    context_report: ContextReport | None = None
    citations: list[RagCitation] = Field(default_factory=list)


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    player_id: ResourceId
    npc_id: ResourceId
    messages: list[ChatMessage]
