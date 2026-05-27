import hashlib
import gc
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import chromadb

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - exercised when ML deps are omitted.
    SentenceTransformer = None

from app.core.config import settings
from app.schemas.rag import RagDocumentChunk, RagDocumentImportResponse
from app.services.token_budget_service import TokenBudgetService


logger = logging.getLogger(__name__)


@dataclass
class ChunkDraft:
    text: str
    heading: str | None = None


class RagKnowledgeService:
    """Chroma-backed document knowledge base for RAG context."""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        embedding_model_name: str,
        token_budget_service: TokenBudgetService | None = None,
        chunk_token_budget: int = 350,
    ) -> None:
        self.client, self.collection = self._build_collection(
            persist_dir=persist_dir,
            collection_name=collection_name,
        )
        self.embedding_model_name = embedding_model_name
        self.token_budget_service = token_budget_service or TokenBudgetService()
        self.chunk_token_budget = max(50, chunk_token_budget)
        self.embedding_model: object | None = None
        self.embedding_model_unavailable = False

    def _build_collection(
        self,
        persist_dir: str,
        collection_name: str,
    ) -> tuple[object, object]:
        try:
            client = chromadb.PersistentClient(path=persist_dir)
            collection = client.get_or_create_collection(name=collection_name)
            return client, collection
        except Exception as exc:
            logger.warning(
                "rag.chroma_persistent_unavailable "
                "persist_dir=%s fallback=in_memory error=%s",
                persist_dir,
                exc,
            )
            client = chromadb.Client()
            collection = client.get_or_create_collection(name=collection_name)
            return client, collection

    def import_document(
        self,
        content: str,
        source: str,
        doc_id: str | None = None,
        title: str | None = None,
        document_format: str = "markdown",
        page: int = 0,
        tags: list[str] | None = None,
    ) -> RagDocumentImportResponse:
        doc_id = doc_id or self._build_doc_id(source, content)
        tags = self._normalize_tags(tags)
        created_at = datetime.now(UTC).isoformat()
        drafts = self._chunk_document(
            content=content,
            document_format=document_format,
            title=title,
        )

        self._delete_existing_doc_chunks(doc_id)

        chunks: list[RagDocumentChunk] = []
        for index, draft in enumerate(drafts):
            chunk_id = f"{doc_id}:{index:04d}"
            chunk = RagDocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                text=draft.text,
                source=source,
                page=page,
                heading=draft.heading,
                created_at=created_at,
                tags=tags,
            )
            chunks.append(chunk)

        if chunks:
            self.collection.add(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                embeddings=[self._encode_text(chunk.text) for chunk in chunks],
                metadatas=[self._metadata_for_chunk(chunk) for chunk in chunks],
            )

        return RagDocumentImportResponse(
            doc_id=doc_id,
            source=source,
            chunks=chunks,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: str | None = None,
        source: str | None = None,
        keyword: str | None = None,
        tags: list[str] | None = None,
    ) -> list[RagDocumentChunk]:
        top_k = max(1, min(top_k, 20))
        if self.collection.count() == 0:
            return []

        where = self._build_where(doc_id=doc_id, source=source)
        query_embedding = self._encode_text(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max(top_k * 4, top_k),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks = self._build_chunks_from_query_results(results)
        chunks = self._filter_chunks(chunks, keyword=keyword, tags=tags)
        ranked_chunks = self._rank_chunks(chunks, query=query, keyword=keyword)
        return ranked_chunks[:top_k]

    def _chunk_document(
        self,
        content: str,
        document_format: str,
        title: str | None,
    ) -> list[ChunkDraft]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        if document_format == "markdown":
            sections = self._split_markdown_sections(normalized, title=title)
        else:
            sections = [ChunkDraft(text=normalized, heading=title)]

        chunks: list[ChunkDraft] = []
        for section in sections:
            for text in self._split_text_to_budget(section.text):
                chunks.append(ChunkDraft(text=text, heading=section.heading))

        return chunks

    def _split_markdown_sections(
        self,
        content: str,
        title: str | None,
    ) -> list[ChunkDraft]:
        sections: list[ChunkDraft] = []
        heading_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []
        current_heading = title

        for line in content.splitlines():
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                self._flush_section(sections, current_lines, current_heading)
                level = len(match.group(1))
                heading = match.group(2).strip()
                heading_stack = [
                    item for item in heading_stack
                    if item[0] < level
                ]
                heading_stack.append((level, heading))
                current_heading = " > ".join(item[1] for item in heading_stack)
                current_lines = [line]
                continue

            current_lines.append(line)

        self._flush_section(sections, current_lines, current_heading)
        return sections or [ChunkDraft(text=content, heading=title)]

    def _flush_section(
        self,
        sections: list[ChunkDraft],
        lines: list[str],
        heading: str | None,
    ) -> None:
        text = "\n".join(lines).strip()
        if text:
            sections.append(ChunkDraft(text=text, heading=heading))

    def _split_text_to_budget(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks: list[str] = []
        current_parts: list[str] = []
        current_tokens = 0

        for paragraph in paragraphs:
            paragraph_tokens = self.token_budget_service.estimate_tokens(paragraph)
            if paragraph_tokens > self.chunk_token_budget:
                if current_parts:
                    chunks.append("\n\n".join(current_parts))
                    current_parts = []
                    current_tokens = 0
                chunks.extend(self._split_oversized_text(paragraph))
                continue

            if current_parts and current_tokens + paragraph_tokens > self.chunk_token_budget:
                chunks.append("\n\n".join(current_parts))
                current_parts = [paragraph]
                current_tokens = paragraph_tokens
                continue

            current_parts.append(paragraph)
            current_tokens += paragraph_tokens

        if current_parts:
            chunks.append("\n\n".join(current_parts))

        return chunks

    def _split_oversized_text(self, text: str) -> list[str]:
        remaining = text.strip()
        chunks: list[str] = []

        while remaining and self.token_budget_service.estimate_tokens(remaining) > self.chunk_token_budget:
            estimated_tokens = self.token_budget_service.estimate_tokens(remaining)
            rough_chars = max(
                1,
                int(len(remaining) * self.chunk_token_budget / max(estimated_tokens, 1)),
            )
            cut_at = self._find_split_index(remaining, rough_chars)
            chunks.append(remaining[:cut_at].strip())
            remaining = remaining[cut_at:].strip()

        if remaining:
            chunks.append(remaining)

        return chunks

    def _find_split_index(self, text: str, preferred_index: int) -> int:
        preferred_index = max(1, min(preferred_index, len(text)))
        lower_bound = max(1, preferred_index // 2)
        candidates = [
            text.rfind(separator, lower_bound, preferred_index)
            for separator in ("\n", "。", ".", "；", ";", "，", ",", " ")
        ]
        split_at = max(candidates)
        if split_at <= 0:
            return preferred_index

        return split_at + 1

    def _delete_existing_doc_chunks(self, doc_id: str) -> None:
        try:
            self.collection.delete(where={"doc_id": {"$eq": doc_id}})
        except Exception:
            logger.debug("rag.delete_existing_chunks_skipped doc_id=%s", doc_id)

    def _metadata_for_chunk(self, chunk: RagDocumentChunk) -> dict[str, object]:
        return {
            "doc_id": chunk.doc_id,
            "source": chunk.source,
            "page": chunk.page,
            "heading": chunk.heading or "",
            "created_at": chunk.created_at,
            "tags": ",".join(chunk.tags),
        }

    def _build_where(
        self,
        doc_id: str | None = None,
        source: str | None = None,
    ) -> dict[str, object] | None:
        clauses: list[dict[str, object]] = []
        if doc_id:
            clauses.append({"doc_id": {"$eq": doc_id}})
        if source:
            clauses.append({"source": {"$eq": source}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _build_chunks_from_query_results(
        self,
        results: dict[str, object],
    ) -> list[RagDocumentChunk]:
        ids_groups = results.get("ids", [])
        documents_groups = results.get("documents", [])
        metadatas_groups = results.get("metadatas", [])
        distances_groups = results.get("distances", [])

        if not ids_groups:
            return []

        ids = ids_groups[0] or []
        documents = documents_groups[0] if documents_groups else []
        metadatas = metadatas_groups[0] if metadatas_groups else []
        distances = distances_groups[0] if distances_groups else []

        chunks: list[RagDocumentChunk] = []
        for index, (chunk_id, document, metadata) in enumerate(zip(ids, documents, metadatas)):
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            distance = distances[index] if index < len(distances) else None
            score = self._distance_to_score(distance)
            tags_text = str(metadata_dict.get("tags", ""))
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

            chunks.append(
                RagDocumentChunk(
                    chunk_id=str(chunk_id),
                    doc_id=str(metadata_dict.get("doc_id", "")),
                    text=document if isinstance(document, str) else str(document or ""),
                    source=str(metadata_dict.get("source", "")),
                    page=int(metadata_dict.get("page") or 0),
                    heading=str(metadata_dict.get("heading") or "") or None,
                    created_at=str(metadata_dict.get("created_at") or ""),
                    tags=tags,
                    score=score,
                )
            )

        return chunks

    def _filter_chunks(
        self,
        chunks: list[RagDocumentChunk],
        keyword: str | None,
        tags: list[str] | None,
    ) -> list[RagDocumentChunk]:
        normalized_keyword = (keyword or "").strip().lower()
        normalized_tags = {tag.strip().lower() for tag in tags or [] if tag.strip()}

        filtered: list[RagDocumentChunk] = []
        for chunk in chunks:
            searchable = " ".join(
                [
                    chunk.text,
                    chunk.source,
                    chunk.heading or "",
                    " ".join(chunk.tags),
                ]
            ).lower()
            if normalized_keyword and normalized_keyword not in searchable:
                continue
            chunk_tags = {tag.lower() for tag in chunk.tags}
            if normalized_tags and not normalized_tags.issubset(chunk_tags):
                continue
            filtered.append(chunk)

        return filtered

    def _rank_chunks(
        self,
        chunks: list[RagDocumentChunk],
        query: str,
        keyword: str | None,
    ) -> list[RagDocumentChunk]:
        terms = self._query_terms(" ".join([query, keyword or ""]))

        ranked: list[RagDocumentChunk] = []
        for chunk in chunks:
            keyword_score = self._keyword_score(chunk, terms)
            base_score = chunk.score or 0.0
            combined_score = base_score + (0.15 * keyword_score)
            ranked.append(chunk.model_copy(update={"score": round(combined_score, 6)}))

        return sorted(
            ranked,
            key=lambda chunk: (chunk.score or 0.0, chunk.created_at, chunk.chunk_id),
            reverse=True,
        )

    def _keyword_score(self, chunk: RagDocumentChunk, terms: set[str]) -> float:
        if not terms:
            return 0.0

        searchable = " ".join(
            [
                chunk.text,
                chunk.source,
                chunk.heading or "",
                " ".join(chunk.tags),
            ]
        ).lower()
        matches = sum(1 for term in terms if term in searchable)
        return matches / max(len(terms), 1)

    def _query_terms(self, text: str) -> set[str]:
        terms = {
            term
            for term in re.findall(r"[A-Za-z0-9_:-]+|[\u4e00-\u9fff]{1,4}", text.lower())
            if term.strip()
        }
        compact = text.strip().lower()
        if compact:
            terms.add(compact)
        return terms

    def _distance_to_score(self, distance: object) -> float | None:
        if distance is None:
            return None
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return None
        return 1.0 / (1.0 + max(0.0, value))

    def _build_doc_id(self, source: str, content: str) -> str:
        digest = hashlib.sha256(f"{source}\n{content}".encode("utf-8")).hexdigest()
        return f"doc_{digest[:16]}"

    def _normalize_tags(self, tags: list[str] | None) -> list[str]:
        if not tags:
            return []
        return [tag.strip() for tag in tags if tag and tag.strip()]

    def _encode_text(self, text: str) -> list[float]:
        if not self.embedding_model_unavailable:
            try:
                if SentenceTransformer is None:
                    raise RuntimeError(
                        "sentence-transformers is not installed; "
                        "install requirements-ml.txt to enable local embeddings"
                    )

                if self.embedding_model is None:
                    self.embedding_model = SentenceTransformer(
                        self.embedding_model_name,
                        local_files_only=settings.EMBEDDING_LOCAL_FILES_ONLY,
                    )

                return self.embedding_model.encode(text).tolist()
            except Exception as exc:
                self.embedding_model_unavailable = True
                logger.warning(
                    "rag.embedding_model_unavailable model=%s fallback=hash_embedding error=%s",
                    self.embedding_model_name,
                    exc,
                )

        return self._hash_embedding(text)

    def _hash_embedding(self, text: str, dimensions: int = 384) -> list[float]:
        vector = [0.0] * dimensions
        tokens = re.findall(r"\w+|[\u4e00-\u9fff]", text.lower())
        if not tokens:
            tokens = [text]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def close(self) -> None:
        self.embedding_model = None
        stop = getattr(getattr(self.client, "_system", None), "stop", None)
        if stop is not None:
            try:
                stop()
            except Exception:
                logger.debug("rag.chroma_stop_failed", exc_info=True)
        gc.collect()
