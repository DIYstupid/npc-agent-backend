from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.dependencies import trace_service
from app.core.exceptions import PromptTraceNotFoundError
from app.schemas.trace import PromptTraceListResponse, PromptTraceRecord
from app.schemas.validation import RESOURCE_ID_MAX_LENGTH, RESOURCE_ID_PATTERN


router = APIRouter(prefix="/debug", tags=["debug"])

RequestIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]


@router.get("/traces", response_model=PromptTraceListResponse)
def list_prompt_traces(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PromptTraceListResponse:
    return PromptTraceListResponse(
        traces=trace_service.list_traces(limit=limit),
    )


@router.get("/traces/latest", response_model=PromptTraceRecord)
def get_latest_prompt_trace() -> PromptTraceRecord:
    trace = trace_service.latest_trace()
    if trace is None:
        raise PromptTraceNotFoundError()

    return trace


@router.get("/traces/{request_id}", response_model=PromptTraceRecord)
def get_prompt_trace(request_id: RequestIdPath) -> PromptTraceRecord:
    trace = trace_service.get_trace(request_id)
    if trace is None:
        raise PromptTraceNotFoundError(request_id)

    return trace
