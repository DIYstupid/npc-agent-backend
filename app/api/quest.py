from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.core.dependencies import game_service, quest_agent
from app.schemas.quest import QuestAgentRequest, QuestAgentResponse, QuestStateResponse
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN


router = APIRouter(prefix="/quest", tags=["quest"])

ResourceIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


@router.post("/run", response_model=QuestAgentResponse)
async def run_quest_agent(request: QuestAgentRequest) -> QuestAgentResponse:
    response = await quest_agent.ainvoke(request)
    if response.player_state is None:
        raise HTTPException(status_code=404, detail="player not found")
    return response


@router.post("/{player_id}/{quest_id}/create", response_model=QuestAgentResponse)
async def create_quest(
    player_id: ResourceIdPath,
    quest_id: ResourceIdPath,
) -> QuestAgentResponse:
    return await run_quest_agent(
        QuestAgentRequest(
            player_id=player_id,
            quest_id=quest_id,
            operation="create",
        )
    )


@router.post("/{player_id}/{quest_id}/advance", response_model=QuestAgentResponse)
async def advance_quest(
    player_id: ResourceIdPath,
    quest_id: ResourceIdPath,
) -> QuestAgentResponse:
    return await run_quest_agent(
        QuestAgentRequest(
            player_id=player_id,
            quest_id=quest_id,
            operation="advance",
        )
    )


@router.post("/{player_id}/{quest_id}/complete", response_model=QuestAgentResponse)
async def complete_quest(
    player_id: ResourceIdPath,
    quest_id: ResourceIdPath,
) -> QuestAgentResponse:
    return await run_quest_agent(
        QuestAgentRequest(
            player_id=player_id,
            quest_id=quest_id,
            operation="complete",
        )
    )


@router.get("/{player_id}", response_model=QuestStateResponse)
def get_player_quests(player_id: ResourceIdPath) -> QuestStateResponse:
    player = game_service.get_player_state(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")

    return QuestStateResponse(
        player_id=player.player_id,
        active_quests=player.active_quests,
        completed_quests=player.completed_quests,
        quest_progress=player.quest_progress,
    )
