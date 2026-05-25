from pydantic import BaseModel, Field

from app.schemas.validation import MemoryText, ResourceId, Tag


class KnowledgeEvent(BaseModel):
    """Shared fact or rumor visible to a controlled set of NPCs and players."""

    event_id: str
    world_id: ResourceId = "default"
    scope: str = "player"
    player_id: ResourceId | None = None
    related_player_ids: list[str] = Field(default_factory=list)
    text: str
    source_npc_id: ResourceId | None = None
    subject_npc_ids: list[str] = Field(default_factory=list)
    known_by_npc_ids: list[str] = Field(default_factory=list)
    location: str | None = None
    event_type: str = "general"
    confidence: float = 1.0
    status: str = "active"
    created_at: str | None = None
    expires_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class KnowledgeEventCreate(BaseModel):
    """Request body for creating a shared knowledge event."""

    text: MemoryText = Field(..., description="Canonical fact or rumor text")
    player_id: ResourceId | None = Field(
        default=None,
        description="Primary player for player-scoped knowledge",
    )
    world_id: ResourceId = Field(default="default", description="World or shard ID")
    scope: str = Field(
        default="player",
        description="Knowledge scope: player, party, world, or npc_private",
    )
    related_player_ids: list[ResourceId] = Field(
        default_factory=list,
        max_length=20,
        description="Players allowed to trigger this knowledge",
    )
    source_npc_id: ResourceId | None = Field(
        default=None,
        description="NPC that originated the event",
    )
    subject_npc_ids: list[ResourceId] = Field(
        default_factory=list,
        max_length=20,
        description="NPCs that the event is about",
    )
    known_by_npc_ids: list[ResourceId] = Field(
        default_factory=list,
        max_length=50,
        description="NPCs that explicitly know this event",
    )
    location: str | None = Field(default=None, max_length=128)
    event_type: str = Field(default="general", min_length=1, max_length=32)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = Field(default="active", min_length=1, max_length=32)
    expires_at: str | None = Field(default=None, max_length=64)
    tags: list[Tag] = Field(default_factory=list, max_length=20)


class KnowledgeEventUpdate(BaseModel):
    """Request body for updating shared knowledge state."""

    text: MemoryText | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    known_by_npc_ids: list[ResourceId] | None = Field(default=None, max_length=50)
    subject_npc_ids: list[ResourceId] | None = Field(default=None, max_length=20)
    related_player_ids: list[ResourceId] | None = Field(default=None, max_length=20)
    tags: list[Tag] | None = Field(default=None, max_length=20)
    expires_at: str | None = Field(default=None, max_length=64)


class KnowledgeEventListResponse(BaseModel):
    """Shared knowledge list response."""

    events: list[KnowledgeEvent]


class KnowledgeEventKnownByResponse(BaseModel):
    """Response for granting an NPC knowledge of an event."""

    event_id: str
    npc_id: str
    known: bool = True


class KnowledgeEventResolveResponse(BaseModel):
    """Response for resolving a shared knowledge event."""

    event_id: str
    status: str = "resolved"
