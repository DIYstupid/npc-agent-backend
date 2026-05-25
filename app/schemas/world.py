from typing import Any

from pydantic import BaseModel, Field

from app.schemas.game import PlayerState, QuestProgressUpdate
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.tool import ToolExecutionResult
from app.schemas.validation import ResourceId


class WorldEventCreate(BaseModel):
    """Request for recording a world event through WorldAgent."""

    text: str = Field(..., min_length=1, max_length=4000)
    player_id: ResourceId | None = None
    world_id: ResourceId = "default"
    scope: str = Field(default="world", max_length=32)
    source_npc_id: ResourceId | None = None
    subject_npc_ids: list[ResourceId] = Field(default_factory=list, max_length=20)
    known_by_npc_ids: list[ResourceId] = Field(default_factory=list, max_length=50)
    location: str | None = Field(default=None, max_length=128)
    event_type: str = Field(default="world_event", min_length=1, max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    world_flags: dict[str, bool] = Field(default_factory=dict)


class WorldAgentResponse(BaseModel):
    """WorldAgent execution result."""

    request_id: str
    world_id: str
    player_id: str | None = None
    status: str
    message: str
    event: KnowledgeEvent | None = None
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)


class WorldInteractionRequest(BaseModel):
    """Natural-language player interaction with the world."""

    player_id: ResourceId
    text: str = Field(..., min_length=1, max_length=4000)
    world_id: ResourceId = "default"
    location: str | None = Field(default=None, max_length=128)
    npc_id: ResourceId | None = None


class WorldTimelineResponse(BaseModel):
    """World event timeline."""

    events: list[KnowledgeEvent]


class WorldActionRequest(BaseModel):
    """Player/world interaction that can update state and advance quests."""

    player_id: ResourceId
    action_type: str = Field(..., min_length=1, max_length=64)
    target_id: ResourceId | None = None
    npc_id: ResourceId | None = None
    location: str | None = Field(default=None, max_length=128)
    world_id: ResourceId = "default"
    payload: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=1000)


class WorldActionResponse(BaseModel):
    """Result of applying a world action."""

    request_id: str
    player_id: str
    action_type: str
    status: str
    message: str
    event: KnowledgeEvent | None = None
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)
    quest_updates: list[QuestProgressUpdate] = Field(default_factory=list)
    player_state: PlayerState | None = None


class WorldInteractionResponse(BaseModel):
    """Result of parsing and applying a natural-language world interaction."""

    request_id: str
    world_id: str
    player_id: str
    status: str
    message: str
    parsed_actions: list[WorldActionRequest] = Field(default_factory=list)
    action_results: list[WorldActionResponse] = Field(default_factory=list)
    events: list[KnowledgeEvent] = Field(default_factory=list)
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)
    quest_updates: list[QuestProgressUpdate] = Field(default_factory=list)
    player_state: PlayerState | None = None
