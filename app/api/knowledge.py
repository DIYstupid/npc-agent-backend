from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.core.dependencies import shared_knowledge_service
from app.schemas.shared_knowledge import (
    KnowledgeEvent,
    KnowledgeEventCreate,
    KnowledgeEventKnownByResponse,
    KnowledgeEventListResponse,
    KnowledgeEventResolveResponse,
    KnowledgeEventUpdate,
)
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN


router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ResourceIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
ResourceIdQuery = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


@router.post("/events", response_model=KnowledgeEvent)
def create_knowledge_event(request: KnowledgeEventCreate) -> KnowledgeEvent:
    return shared_knowledge_service.publish_event(
        text=request.text,
        player_id=request.player_id,
        world_id=request.world_id,
        scope=request.scope,
        related_player_ids=request.related_player_ids,
        source_npc_id=request.source_npc_id,
        subject_npc_ids=request.subject_npc_ids,
        known_by_npc_ids=request.known_by_npc_ids,
        location=request.location,
        event_type=request.event_type,
        confidence=request.confidence,
        status=request.status,
        expires_at=request.expires_at,
        tags=request.tags,
    )


@router.get("/events", response_model=KnowledgeEventListResponse)
def list_knowledge_events(
    world_id: str = "default",
    player_id: ResourceIdQuery = None,
    npc_id: ResourceIdQuery = None,
    status: str | None = "active",
    event_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> KnowledgeEventListResponse:
    events = shared_knowledge_service.list_events(
        world_id=world_id,
        player_id=player_id,
        npc_id=npc_id,
        status=status,
        event_type=event_type,
        limit=limit,
    )
    return KnowledgeEventListResponse(events=events)


@router.get("/events/{event_id}", response_model=KnowledgeEvent)
def get_knowledge_event(event_id: ResourceIdPath) -> KnowledgeEvent:
    event = shared_knowledge_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="knowledge event not found")
    return event


@router.patch("/events/{event_id}", response_model=KnowledgeEvent)
def update_knowledge_event(
    event_id: ResourceIdPath,
    request: KnowledgeEventUpdate,
) -> KnowledgeEvent:
    event = shared_knowledge_service.update_event(
        event_id=event_id,
        text=request.text,
        status=request.status,
        confidence=request.confidence,
        known_by_npc_ids=request.known_by_npc_ids,
        subject_npc_ids=request.subject_npc_ids,
        related_player_ids=request.related_player_ids,
        tags=request.tags,
        expires_at=request.expires_at,
    )
    if event is None:
        raise HTTPException(status_code=404, detail="knowledge event not found")
    return event


@router.post("/events/{event_id}/known-by/{npc_id}", response_model=KnowledgeEventKnownByResponse)
def mark_knowledge_known(
    event_id: ResourceIdPath,
    npc_id: ResourceIdPath,
) -> KnowledgeEventKnownByResponse:
    event = shared_knowledge_service.mark_known_by(
        event_id=event_id,
        npc_id=npc_id,
    )
    if event is None:
        raise HTTPException(status_code=404, detail="knowledge event not found")
    return KnowledgeEventKnownByResponse(event_id=event_id, npc_id=npc_id)


@router.post("/events/{event_id}/resolve", response_model=KnowledgeEventResolveResponse)
def resolve_knowledge_event(event_id: ResourceIdPath) -> KnowledgeEventResolveResponse:
    event = shared_knowledge_service.resolve_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="knowledge event not found")
    return KnowledgeEventResolveResponse(event_id=event.event_id, status=event.status)
