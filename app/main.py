from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import FastAPI, Path

from app.api.chat import router as chat_router
from app.api.debug import router as debug_router
from app.api.knowledge import router as knowledge_router
from app.api.memory import router as memory_router
from app.api.quest import router as quest_router
from app.api.world import router as world_router
from app.core.config import settings
from app.core.dependencies import close_resources, game_service
from app.core.exceptions import NpcNotFoundError, PlayerNotFoundError, register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import SimpleRateLimitMiddleware
from app.schemas.npc import NPCProfile
from app.schemas.game import PlayerState
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN
from app.services.npc_service import NPCService


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        close_resources()


app = FastAPI(
    title="NPC Agent Backend",
    description="基于 LLM Agent 的游戏 NPC 行为决策与对话后端系统",
    version="0.5.0",
    lifespan=lifespan,
)

if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        excluded_paths=settings.RATE_LIMIT_EXCLUDED_PATHS,
    )

register_exception_handlers(app)

app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(knowledge_router)
app.include_router(quest_router)
app.include_router(world_router)
app.include_router(debug_router)

npc_service = NPCService()

ResourceIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "npc-agent-backend",
        "version": "0.5.0",
    }


@app.get("/npcs", response_model=list[NPCProfile])
def list_npcs() -> list[NPCProfile]:
    return npc_service.list_npcs()


@app.get("/npcs/{npc_id}", response_model=NPCProfile)
def get_npc(npc_id: ResourceIdPath) -> NPCProfile:
    npc = npc_service.get_npc(npc_id)

    if npc is None:
        raise NpcNotFoundError(npc_id)

    return npc


@app.get("/game/state/{player_id}", response_model=PlayerState)
def get_game_state(player_id: ResourceIdPath) -> PlayerState:
    player_state = game_service.get_player_state(player_id)

    if player_state is None:
        raise PlayerNotFoundError(player_id)

    return player_state
