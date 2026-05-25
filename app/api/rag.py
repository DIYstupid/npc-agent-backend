from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import rag_knowledge_service
from app.schemas.rag import (
    RagDocumentImportRequest,
    RagDocumentImportResponse,
    RagSearchResponse,
)
from app.schemas.validation import SEARCH_QUERY_MAX_LENGTH


router = APIRouter(prefix="/rag", tags=["rag"])

SearchQueryParam = Annotated[
    str,
    Query(
        min_length=1,
        max_length=SEARCH_QUERY_MAX_LENGTH,
    ),
]


@router.post("/documents", response_model=RagDocumentImportResponse)
def import_rag_document(
    request: RagDocumentImportRequest,
) -> RagDocumentImportResponse:
    return rag_knowledge_service.import_document(
        content=request.content,
        source=request.source,
        doc_id=request.doc_id,
        title=request.title,
        document_format=request.document_format,
        page=request.page,
        tags=request.tags,
    )


@router.get("/search", response_model=RagSearchResponse)
def search_rag_documents(
    query: SearchQueryParam,
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
    doc_id: Annotated[str | None, Query(max_length=128)] = None,
    source: Annotated[str | None, Query(max_length=512)] = None,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    tags: Annotated[list[str] | None, Query(max_length=20)] = None,
) -> RagSearchResponse:
    chunks = rag_knowledge_service.search(
        query=query,
        top_k=top_k,
        doc_id=doc_id,
        source=source,
        keyword=keyword,
        tags=tags or [],
    )
    return RagSearchResponse(
        query=query,
        chunks=chunks,
    )
