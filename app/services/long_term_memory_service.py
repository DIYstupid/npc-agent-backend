import hashlib
import logging
import math
import re
import uuid
from datetime import UTC, datetime

import chromadb

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - exercised when ML deps are omitted.
    SentenceTransformer = None

from app.core.config import settings
from app.schemas.memory import LongTermMemory


logger = logging.getLogger(__name__)


class LongTermMemoryService:
    """
    Chroma 版长期记忆服务。

    用途：
    - 保存玩家和 NPC 之间的重要事件
    - 通过语义相似度检索相关长期记忆

    数据隔离：
    - npc_id
    - player_id
    """

    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        embedding_model_name: str,
    ) -> None:
        self.client, self.collection = self._build_collection(
            persist_dir=persist_dir,
            collection_name=collection_name,
        )

        self.embedding_model_name = embedding_model_name
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
                "long_term_memory.chroma_persistent_unavailable "
                "persist_dir=%s fallback=in_memory error=%s",
                persist_dir,
                exc,
            )
            client = chromadb.Client()
            collection = client.get_or_create_collection(name=collection_name)
            return client, collection

    def add_memory(
        self,
        npc_id: str,
        player_id: str,
        text: str,
        importance: int = 1,
        memory_type: str = "general",
        tags: list[str] | None = None,
    ) -> LongTermMemory:
        memory_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        memory_type = memory_type or "general"
        tags = self._normalize_tags(tags)

        embedding = self._encode_text(text)

        self.collection.add(
            ids=[memory_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[
                self._build_metadata(
                    npc_id=npc_id,
                    player_id=player_id,
                    importance=importance,
                    memory_type=memory_type,
                    tags=tags,
                    created_at=created_at,
                )
            ],
        )

        return LongTermMemory(
            memory_id=memory_id,
            npc_id=npc_id,
            player_id=player_id,
            text=text,
            memory_type=memory_type,
            importance=importance,
            created_at=created_at,
            tags=tags,
        )

    def list_memories(
        self,
        npc_id: str,
        player_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[LongTermMemory]:
        results = self.collection.get(
            where=self._build_where(
                npc_id=npc_id,
                player_id=player_id,
                memory_type=memory_type,
            ),
            limit=max(1, limit),
            include=["documents", "metadatas"],
        )

        memories = self._build_memories_from_get_results(results)
        return self._sort_memories(memories)

    def get_memory(self, memory_id: str) -> LongTermMemory | None:
        results = self.collection.get(
            ids=[memory_id],
            include=["documents", "metadatas"],
        )
        memories = self._build_memories_from_get_results(results)
        if not memories:
            return None

        return memories[0]

    def update_memory(
        self,
        memory_id: str,
        text: str | None = None,
        importance: int | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
    ) -> LongTermMemory | None:
        existing_memory = self.get_memory(memory_id)
        if existing_memory is None:
            return None

        created_at = existing_memory.created_at or datetime.now(UTC).isoformat()
        updated_memory_type = existing_memory.memory_type
        if memory_type is not None:
            updated_memory_type = memory_type or "general"

        updated_memory = existing_memory.model_copy(
            update={
                "text": text if text is not None else existing_memory.text,
                "importance": (
                    importance if importance is not None else existing_memory.importance
                ),
                "memory_type": updated_memory_type,
                "tags": (
                    self._normalize_tags(tags)
                    if tags is not None
                    else existing_memory.tags
                ),
                "created_at": created_at,
            }
        )

        self.collection.update(
            ids=[memory_id],
            documents=[updated_memory.text],
            embeddings=[self._encode_text(updated_memory.text)],
            metadatas=[
                self._build_metadata(
                    npc_id=updated_memory.npc_id,
                    player_id=updated_memory.player_id,
                    importance=updated_memory.importance,
                    memory_type=updated_memory.memory_type,
                    tags=updated_memory.tags,
                    created_at=updated_memory.created_at,
                )
            ],
        )

        return updated_memory

    def delete_memory(self, memory_id: str) -> bool:
        existing_memory = self.get_memory(memory_id)
        if existing_memory is None:
            return False

        self.collection.delete(ids=[memory_id])
        return True

    def search_memory(
        self,
        npc_id: str,
        player_id: str,
        query: str,
        top_k: int = 3,
        memory_type: str | None = None,
    ) -> list[LongTermMemory]:
        query_embedding = self._encode_text(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=self._build_where(
                npc_id=npc_id,
                player_id=player_id,
                memory_type=memory_type,
            ),
            include=["documents", "metadatas"],
        )

        return self._build_memories_from_query_results(results)

    def _build_metadata(
        self,
        npc_id: str,
        player_id: str,
        importance: int,
        memory_type: str,
        tags: list[str],
        created_at: str | None,
    ) -> dict[str, object]:
        return {
            "npc_id": npc_id,
            "player_id": player_id,
            "importance": importance,
            "memory_type": memory_type or "general",
            "tags": ",".join(tags),
            "created_at": created_at or datetime.now(UTC).isoformat(),
        }

    def _build_where(
        self,
        npc_id: str,
        player_id: str,
        memory_type: str | None = None,
    ) -> dict[str, object]:
        clauses: list[dict[str, object]] = [
            {"npc_id": {"$eq": npc_id}},
            {"player_id": {"$eq": player_id}},
        ]

        if memory_type:
            clauses.append({"memory_type": {"$eq": memory_type}})

        if len(clauses) == 1:
            return clauses[0]

        return {"$and": clauses}

    def _build_memories_from_query_results(
        self,
        results: dict[str, object],
    ) -> list[LongTermMemory]:
        ids_groups = results.get("ids", [])
        documents_groups = results.get("documents", [])
        metadatas_groups = results.get("metadatas", [])

        if not ids_groups:
            return []

        ids = ids_groups[0] or []
        documents = documents_groups[0] if documents_groups else []
        metadatas = metadatas_groups[0] if metadatas_groups else []

        return self._build_memories(ids, documents, metadatas)

    def _build_memories_from_get_results(
        self,
        results: dict[str, object],
    ) -> list[LongTermMemory]:
        ids = results.get("ids", []) or []
        documents = results.get("documents", []) or []
        metadatas = results.get("metadatas", []) or []

        return self._build_memories(ids, documents, metadatas)

    def _build_memories(
        self,
        ids: list[object],
        documents: list[object],
        metadatas: list[object],
    ) -> list[LongTermMemory]:
        memories: list[LongTermMemory] = []

        for memory_id, document, metadata in zip(ids, documents, metadatas):
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            text = document if isinstance(document, str) else str(document or "")
            tags_text = str(metadata_dict.get("tags", ""))
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

            memories.append(
                LongTermMemory(
                    memory_id=str(memory_id),
                    npc_id=str(metadata_dict.get("npc_id", "")),
                    player_id=str(metadata_dict.get("player_id", "")),
                    text=text,
                    memory_type=str(metadata_dict.get("memory_type") or "general"),
                    importance=int(metadata_dict.get("importance") or 1),
                    created_at=metadata_dict.get("created_at"),
                    tags=tags,
                )
            )

        return memories

    def _sort_memories(
        self,
        memories: list[LongTermMemory],
    ) -> list[LongTermMemory]:
        return sorted(
            memories,
            key=lambda memory: (
                memory.created_at or "",
                memory.importance,
                memory.memory_id,
            ),
            reverse=True,
        )

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
                    "long_term_memory.embedding_model_unavailable "
                    "model=%s fallback=hash_embedding error=%s",
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
