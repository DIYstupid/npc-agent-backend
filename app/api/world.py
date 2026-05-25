from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import shared_knowledge_service, world_action_service, world_agent
from app.schemas.world import (
    WorldActionRequest,
    WorldActionResponse,
    WorldAgentResponse,
    WorldEventCreate,
    WorldInteractionRequest,
    WorldInteractionResponse,
    WorldTimelineResponse,
)


router = APIRouter(prefix="/world", tags=["world"])


@router.post("/events", response_model=WorldAgentResponse)
async def create_world_event(request: WorldEventCreate) -> WorldAgentResponse:
    return await world_agent.ainvoke(request)


@router.post("/interactions", response_model=WorldInteractionResponse)
async def apply_world_interaction(request: WorldInteractionRequest) -> WorldInteractionResponse:
    return await world_agent.interact(request)


@router.post("/actions", response_model=WorldActionResponse)
async def apply_world_action(request: WorldActionRequest) -> WorldActionResponse:
    return await world_action_service.apply_action(request)


@router.get("/events", response_model=WorldTimelineResponse)
def list_world_events(
    world_id: str = "default",
    player_id: str | None = None,
    npc_id: str | None = None,
    status: str | None = "active",
    event_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorldTimelineResponse:
    return WorldTimelineResponse(
        events=shared_knowledge_service.list_events(
            world_id=world_id,
            player_id=player_id,
            npc_id=npc_id,
            status=status,
            event_type=event_type,
            limit=limit,
        )
    )
