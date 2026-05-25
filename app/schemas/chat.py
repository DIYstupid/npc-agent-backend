from pydantic import BaseModel, Field

from app.schemas.context import ContextReport
from app.schemas.tool import ToolExecutionResult
from app.schemas.validation import ChatText, ResourceId


class ChatRequest(BaseModel):
    """Player chat request."""

    player_id: ResourceId = Field(..., description="Player ID")
    message: ChatText = Field(..., description="Player input")


class ChatMessage(BaseModel):
    """Short-term chat message."""

    role: str = Field(..., description="Message role, such as player or npc")
    content: str = Field(..., description="Message content")


class AgentAction(BaseModel):
    """Structured action emitted by the NPC agent."""

    tool: str = Field(..., description="Tool name")
    args: dict = Field(
        default_factory=dict,
        max_length=20,
        description="Tool arguments",
    )


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


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    player_id: ResourceId
    npc_id: ResourceId
    messages: list[ChatMessage]
