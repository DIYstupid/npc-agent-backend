from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel

from app.core.dependencies import long_term_memory_service, memory_service
from app.core.exceptions import LongTermMemoryNotFoundError
from app.schemas.memory import (
    LongTermMemory,
    LongTermMemoryCreate,
    LongTermMemoryDeleteResponse,
    LongTermMemoryListResponse,
    LongTermMemoryUpdate,
)
from app.schemas.validation import (
    MEMORY_TYPE_MAX_LENGTH,
    RESOURCE_ID_MAX_LENGTH,
    RESOURCE_ID_PATTERN,
    SEARCH_QUERY_MAX_LENGTH,
)


router = APIRouter(prefix="/memory", tags=["memory"])

ResourceIdQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
ResourceIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
MemoryTypeQuery = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=MEMORY_TYPE_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
SearchQueryParam = Annotated[
    str,
    Query(
        min_length=1,
        max_length=SEARCH_QUERY_MAX_LENGTH,
    ),
]


class SessionSummaryResponse(BaseModel):
    player_id: str
    npc_id: str
    summary: str


@router.post("/long-term", response_model=LongTermMemory)
def create_long_term_memory(
    request: LongTermMemoryCreate,
) -> LongTermMemory:
    return long_term_memory_service.add_memory(
        npc_id=request.npc_id,
        player_id=request.player_id,
        text=request.text,
        importance=request.importance,
        memory_type=request.memory_type,
        tags=request.tags,
    )


@router.get("/long-term", response_model=LongTermMemoryListResponse)
def list_long_term_memory(
    npc_id: ResourceIdQuery,
    player_id: ResourceIdQuery,
    memory_type: MemoryTypeQuery = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LongTermMemoryListResponse:
    memories = long_term_memory_service.list_memories(
        npc_id=npc_id,
        player_id=player_id,
        memory_type=memory_type,
        limit=limit,
    )

    return LongTermMemoryListResponse(
        npc_id=npc_id,
        player_id=player_id,
        memories=memories,
    )


@router.get("/long-term/search", response_model=list[LongTermMemory])
def search_long_term_memory(
    npc_id: ResourceIdQuery,
    player_id: ResourceIdQuery,
    query: SearchQueryParam,
    top_k: Annotated[int, Query(ge=1, le=10)] = 3,
    memory_type: MemoryTypeQuery = None,
) -> list[LongTermMemory]:
    return long_term_memory_service.search_memory(
        npc_id=npc_id,
        player_id=player_id,
        query=query,
        top_k=top_k,
        memory_type=memory_type,
    )


@router.patch("/long-term/{memory_id}", response_model=LongTermMemory)
def update_long_term_memory(
    memory_id: ResourceIdPath,
    request: LongTermMemoryUpdate,
) -> LongTermMemory:
    updated_memory = long_term_memory_service.update_memory(
        memory_id=memory_id,
        text=request.text,
        importance=request.importance,
        memory_type=request.memory_type,
        tags=request.tags,
    )

    if updated_memory is None:
        raise LongTermMemoryNotFoundError(memory_id)

    return updated_memory


@router.delete("/long-term/{memory_id}", response_model=LongTermMemoryDeleteResponse)
def delete_long_term_memory(memory_id: ResourceIdPath) -> LongTermMemoryDeleteResponse:
    deleted = long_term_memory_service.delete_memory(memory_id)

    if not deleted:
        raise LongTermMemoryNotFoundError(memory_id)

    return LongTermMemoryDeleteResponse(
        memory_id=memory_id,
        deleted=True,
        status="deleted",
    )


@router.get("/summary/{player_id}/{npc_id}", response_model=SessionSummaryResponse)
def get_session_summary(
    player_id: ResourceIdPath,
    npc_id: ResourceIdPath,
) -> SessionSummaryResponse:
    get_summary = getattr(memory_service, "get_summary", None)
    summary = ""
    if get_summary is not None:
        summary = get_summary(
            player_id=player_id,
            npc_id=npc_id,
        )

    return SessionSummaryResponse(
        player_id=player_id,
        npc_id=npc_id,
        summary=summary,
    )
