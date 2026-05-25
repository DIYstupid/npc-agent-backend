from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.validation import SearchQuery, Tag


DocumentFormat = Literal["markdown", "txt"]

SourceText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=512,
    ),
]

DocumentId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
    ),
]


class RagDocumentImportRequest(BaseModel):
    """Request body for importing one knowledge base document."""

    content: str = Field(..., min_length=1, max_length=200_000)
    source: SourceText = Field(..., description="Human-readable document source")
    doc_id: DocumentId | None = Field(default=None, description="Stable document ID")
    title: str | None = Field(default=None, max_length=200)
    document_format: DocumentFormat = Field(default="markdown")
    page: int = Field(default=0, ge=0)
    tags: list[Tag] = Field(default_factory=list, max_length=20)


class RagDocumentChunk(BaseModel):
    """One indexed RAG chunk."""

    chunk_id: str
    doc_id: str
    text: str
    source: str
    page: int = 0
    heading: str | None = None
    created_at: str
    tags: list[str] = Field(default_factory=list)
    score: float | None = None


class RagCitation(BaseModel):
    """Citation returned with chat answers that used RAG context."""

    chunk_id: str
    doc_id: str
    source: str
    page: int = 0
    heading: str | None = None
    score: float | None = None


class RagDocumentImportResponse(BaseModel):
    doc_id: str
    source: str
    chunks: list[RagDocumentChunk]


class RagSearchResponse(BaseModel):
    query: str
    chunks: list[RagDocumentChunk]


class RagSearchRequest(BaseModel):
    query: SearchQuery
    top_k: int = Field(default=5, ge=1, le=20)
    doc_id: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=512)
    keyword: str | None = Field(default=None, max_length=100)
    tags: list[Tag] = Field(default_factory=list, max_length=20)
