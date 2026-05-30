from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.core.dependencies import story_import_service
from app.schemas.story import (
    StoryActivationRequest,
    StoryActivationResponse,
    StoryDocumentImportRequest,
    StoryImportPreview,
    StoryRecord,
)
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN
from app.services.story_import_service import StoryActivationError


router = APIRouter(prefix="/story", tags=["story"])

StoryIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


@router.post("/import", response_model=StoryImportPreview)
def import_story_document(
    request: StoryDocumentImportRequest,
) -> StoryImportPreview:
    return story_import_service.import_story(
        content=request.content,
        source=request.source,
        title=request.title,
        activate=request.activate,
        player_id=request.player_id,
    )


@router.get("/{story_id}", response_model=StoryRecord)
def get_story(story_id: StoryIdPath) -> StoryRecord:
    record = story_import_service.get_story(story_id)
    if record is None:
        raise HTTPException(status_code=404, detail="story not found")
    return record


@router.post("/{story_id}/activate", response_model=StoryActivationResponse)
def activate_story(
    story_id: StoryIdPath,
    request: StoryActivationRequest | None = None,
) -> StoryActivationResponse:
    try:
        response = story_import_service.activate_story(
            story_id=story_id,
            player_id=request.player_id if request is not None else None,
        )
    except StoryActivationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "validation": exc.validation.model_dump(mode="json"),
            },
        ) from exc

    if response is None:
        raise HTTPException(status_code=404, detail="story not found")
    return response
