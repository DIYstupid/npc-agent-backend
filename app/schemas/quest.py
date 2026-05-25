from pydantic import BaseModel, Field

from app.schemas.game import PlayerState, QuestObjective, QuestProgress
from app.schemas.tool import ToolExecutionResult
from app.schemas.validation import ResourceId


class QuestAgentRequest(BaseModel):
    """Request for advancing quest state through QuestAgent."""

    player_id: ResourceId
    quest_id: ResourceId
    operation: str = Field(
        default="advance",
        description="Quest operation: create, advance, or complete",
    )
    note: str | None = Field(default=None, max_length=1000)
    objectives: list[QuestObjective] = Field(default_factory=list, max_length=20)


class QuestAgentResponse(BaseModel):
    """QuestAgent execution result."""

    request_id: str
    player_id: str
    quest_id: str
    operation: str
    status: str
    message: str
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)
    player_state: PlayerState | None = None


class QuestStateResponse(BaseModel):
    """Current quest state for a player."""

    player_id: str
    active_quests: list[str] = Field(default_factory=list)
    completed_quests: list[str] = Field(default_factory=list)
    quest_progress: dict[str, QuestProgress] = Field(default_factory=dict)
