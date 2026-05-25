from pydantic import BaseModel, Field

from app.schemas.validation import MemoryText, MemoryType, ResourceId, SearchQuery, Tag


class LongTermMemoryCreate(BaseModel):
    """Request body for creating a long-term memory."""

    npc_id: ResourceId = Field(..., description="NPC ID")
    player_id: ResourceId = Field(..., description="Player ID")
    text: MemoryText = Field(..., description="Memory text")
    importance: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Memory importance, 1 to 10",
    )
    memory_type: MemoryType = Field(
        default="general",
        description="Memory type, such as profile, quest, relationship, or world_event",
    )
    tags: list[Tag] = Field(
        default_factory=list,
        max_length=20,
        description="Memory tags",
    )


class LongTermMemory(BaseModel):
    """A long-term memory record."""

    memory_id: str
    npc_id: ResourceId
    player_id: ResourceId
    text: str
    memory_type: str = "general"
    importance: int = 1
    created_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class LongTermMemoryUpdate(BaseModel):
    """Request body for updating a long-term memory."""

    text: MemoryText | None = Field(default=None, description="Memory text")
    importance: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Memory importance, 1 to 10",
    )
    memory_type: MemoryType | None = Field(
        default=None,
        description="Memory type",
    )
    tags: list[Tag] | None = Field(
        default=None,
        max_length=20,
        description="Memory tags",
    )


class LongTermMemorySearchRequest(BaseModel):
    """Request body for searching long-term memory."""

    query: SearchQuery = Field(..., description="Search query")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of results")
    memory_type: MemoryType | None = Field(
        default=None,
        description="Optional memory type filter",
    )


class LongTermMemorySearchResponse(BaseModel):
    """Long-term memory search response."""

    npc_id: ResourceId
    player_id: ResourceId
    query: str
    memories: list[LongTermMemory]


class LongTermMemoryListResponse(BaseModel):
    """Long-term memory list response."""

    npc_id: ResourceId
    player_id: ResourceId
    memories: list[LongTermMemory]


class LongTermMemoryDeleteResponse(BaseModel):
    """Long-term memory delete response."""

    memory_id: str
    deleted: bool = True
    status: str = "deleted"
