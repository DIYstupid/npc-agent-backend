from typing import Annotated

from fastapi import APIRouter, Path
from fastapi.responses import StreamingResponse

from app.core.dependencies import (
    context_builder_service,
    game_service,
    chat_service,
    memory_service,
    long_term_memory_service,
    rag_knowledge_service,
    shared_knowledge_service,
)
from app.core.exceptions import NpcNotFoundError, PlayerNotFoundError
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN
from app.services.npc_service import NPCService


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

npc_service = NPCService()

ResourceIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


def _resolve_chat_targets(npc_id: str, player_id: str):
    npc = npc_service.get_npc(npc_id)
    if npc is None:
        raise NpcNotFoundError(npc_id)

    player_state = game_service.get_player_state(player_id)
    if player_state is None:
        raise PlayerNotFoundError(player_id)

    return npc, player_state


@router.post("/{npc_id}", response_model=ChatResponse)
def chat_with_npc(npc_id: ResourceIdPath, request: ChatRequest) -> ChatResponse:
    npc, player_state = _resolve_chat_targets(npc_id, request.player_id)

    return chat_service.chat(
        npc=npc,
        player_state=player_state,
        message=request.message,
    )


@router.post("/{npc_id}/stream")
def stream_chat_with_npc(npc_id: ResourceIdPath, request: ChatRequest) -> StreamingResponse:
    npc, player_state = _resolve_chat_targets(npc_id, request.player_id)

    return StreamingResponse(
        chat_service.stream_chat(
            npc=npc,
            player_state=player_state,
            message=request.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{player_id}/{npc_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    player_id: ResourceIdPath,
    npc_id: ResourceIdPath,
) -> ChatHistoryResponse:
    npc = npc_service.get_npc(npc_id)
    if npc is None:
        raise NpcNotFoundError(npc_id)

    player_state = game_service.get_player_state(player_id)
    if player_state is None:
        raise PlayerNotFoundError(player_id)

    messages = memory_service.get_messages(
        player_id=player_id,
        npc_id=npc_id,
    )

    return ChatHistoryResponse(
        player_id=player_id,
        npc_id=npc_id,
        messages=messages,
    )


@router.delete("/history/{player_id}/{npc_id}")
def clear_chat_history(player_id: ResourceIdPath, npc_id: ResourceIdPath) -> dict:
    npc = npc_service.get_npc(npc_id)
    if npc is None:
        raise NpcNotFoundError(npc_id)

    player_state = game_service.get_player_state(player_id)
    if player_state is None:
        raise PlayerNotFoundError(player_id)

    memory_service.clear_messages(
        player_id=player_id,
        npc_id=npc_id,
    )

    return {
        "status": "ok",
        "message": "chat history cleared",
        "player_id": player_id,
        "npc_id": npc_id,
    }


@router.post("/{npc_id}/debug-prompt")
def debug_prompt(npc_id: ResourceIdPath, request: ChatRequest) -> dict:
    npc = npc_service.get_npc(npc_id)
    if npc is None:
        raise NpcNotFoundError(npc_id)

    player_state = game_service.get_player_state(request.player_id)
    if player_state is None:
        raise PlayerNotFoundError(request.player_id)

    short_term_memory = memory_service.get_messages(
        player_id=request.player_id,
        npc_id=npc_id,
    )

    get_summary = getattr(memory_service, "get_summary", None)
    summary_memory = ""
    if get_summary is not None:
        summary_memory = get_summary(
            player_id=request.player_id,
            npc_id=npc_id,
        )

    long_term_memory = long_term_memory_service.search_memory(
        npc_id=npc_id,
        player_id=request.player_id,
        query=request.message,
        top_k=3,
    )
    shared_knowledge = shared_knowledge_service.get_relevant_events(
        player_id=request.player_id,
        npc_id=npc_id,
        query=request.message,
        top_k=3,
    )
    rag_chunks = rag_knowledge_service.search(
        query=request.message,
        top_k=3,
    )

    built_context = context_builder_service.build(
        request_id="debug-prompt",
        npc=npc,
        player_state=player_state,
        player_message=request.message,
        short_term_memory=short_term_memory,
        summary_memory=summary_memory,
        long_term_memory=long_term_memory,
        shared_knowledge=shared_knowledge,
        rag_chunks=rag_chunks,
    )

    return {
        "npc_id": npc_id,
        "player_id": request.player_id,
        "prompt": built_context.prompt,
        "context_report": built_context.report,
        "shared_knowledge": built_context.selected_shared_knowledge,
        "rag_chunks": built_context.selected_rag_chunks,
    }
