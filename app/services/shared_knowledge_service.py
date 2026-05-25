import uuid

from app.repositories.shared_knowledge_repository import SharedKnowledgeRepository
from app.schemas.shared_knowledge import KnowledgeEvent


ACTIVE_KNOWLEDGE_STATUS = "active"
RESOLVED_KNOWLEDGE_STATUS = "resolved"


class SharedKnowledgeService:
    """Domain service for cross-NPC information sharing and visibility."""

    def __init__(self, repository: SharedKnowledgeRepository) -> None:
        self.repository = repository

    def publish_event(
        self,
        text: str,
        player_id: str | None = None,
        world_id: str = "default",
        scope: str = "player",
        related_player_ids: list[str] | None = None,
        source_npc_id: str | None = None,
        subject_npc_ids: list[str] | None = None,
        known_by_npc_ids: list[str] | None = None,
        location: str | None = None,
        event_type: str = "general",
        confidence: float = 1.0,
        status: str = ACTIVE_KNOWLEDGE_STATUS,
        expires_at: str | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeEvent:
        event = KnowledgeEvent(
            event_id=str(uuid.uuid4()),
            world_id=world_id or "default",
            scope=scope or "player",
            player_id=player_id,
            related_player_ids=list(related_player_ids or []),
            text=text,
            source_npc_id=source_npc_id,
            subject_npc_ids=list(subject_npc_ids or []),
            known_by_npc_ids=list(known_by_npc_ids or []),
            location=location,
            event_type=event_type or "general",
            confidence=confidence,
            status=status or ACTIVE_KNOWLEDGE_STATUS,
            expires_at=expires_at,
            tags=list(tags or []),
        )
        return self.repository.add_event(event)

    def get_event(self, event_id: str) -> KnowledgeEvent | None:
        return self.repository.get_event(event_id)

    def list_events(
        self,
        world_id: str = "default",
        player_id: str | None = None,
        npc_id: str | None = None,
        status: str | None = ACTIVE_KNOWLEDGE_STATUS,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        return self.repository.list_events(
            world_id=world_id,
            player_id=player_id,
            npc_id=npc_id,
            status=status,
            event_type=event_type,
            limit=limit,
        )

    def get_relevant_events(
        self,
        player_id: str,
        npc_id: str,
        query: str,
        world_id: str = "default",
        top_k: int = 5,
    ) -> list[KnowledgeEvent]:
        events = self.repository.list_events(
            world_id=world_id,
            player_id=player_id,
            npc_id=npc_id,
            status=ACTIVE_KNOWLEDGE_STATUS,
            limit=100,
        )

        ranked_events = sorted(
            events,
            key=lambda event: self._score_event(event=event, npc_id=npc_id, query=query),
            reverse=True,
        )
        return ranked_events[: max(1, top_k)]

    def mark_known_by(self, event_id: str, npc_id: str) -> KnowledgeEvent | None:
        event = self.repository.get_event(event_id)
        if event is None:
            return None

        if npc_id not in event.known_by_npc_ids:
            event = event.model_copy(
                update={
                    "known_by_npc_ids": [
                        *event.known_by_npc_ids,
                        npc_id,
                    ]
                }
            )
            event = self.repository.update_event(event)

        return event

    def resolve_event(self, event_id: str) -> KnowledgeEvent | None:
        event = self.repository.get_event(event_id)
        if event is None:
            return None

        resolved_event = event.model_copy(
            update={
                "status": RESOLVED_KNOWLEDGE_STATUS,
            }
        )
        return self.repository.update_event(resolved_event)

    def update_event(
        self,
        event_id: str,
        text: str | None = None,
        status: str | None = None,
        confidence: float | None = None,
        known_by_npc_ids: list[str] | None = None,
        subject_npc_ids: list[str] | None = None,
        related_player_ids: list[str] | None = None,
        tags: list[str] | None = None,
        expires_at: str | None = None,
    ) -> KnowledgeEvent | None:
        event = self.repository.get_event(event_id)
        if event is None:
            return None

        updates: dict[str, object] = {}
        if text is not None:
            updates["text"] = text
        if status is not None:
            updates["status"] = status
        if confidence is not None:
            updates["confidence"] = confidence
        if known_by_npc_ids is not None:
            updates["known_by_npc_ids"] = known_by_npc_ids
        if subject_npc_ids is not None:
            updates["subject_npc_ids"] = subject_npc_ids
        if related_player_ids is not None:
            updates["related_player_ids"] = related_player_ids
        if tags is not None:
            updates["tags"] = tags
        if expires_at is not None:
            updates["expires_at"] = expires_at

        if not updates:
            return event

        return self.repository.update_event(event.model_copy(update=updates))

    def _score_event(self, event: KnowledgeEvent, npc_id: str, query: str) -> tuple[int, float, str]:
        score = 0
        query_terms = self._terms(query)
        searchable_terms = self._terms(
            " ".join(
                [
                    event.text,
                    event.event_type,
                    event.location or "",
                    " ".join(event.tags),
                ]
            )
        )

        if npc_id == event.source_npc_id:
            score += 3
        if npc_id in event.subject_npc_ids:
            score += 3
        if npc_id in event.known_by_npc_ids:
            score += 2

        score += len(query_terms & searchable_terms)

        return (score, event.confidence, event.created_at or "")

    def _terms(self, text: str) -> set[str]:
        return {
            term.strip().lower()
            for term in text.replace(",", " ").replace("，", " ").split()
            if term.strip()
        }

    def close(self) -> None:
        close_repository = getattr(self.repository, "close", None)
        if close_repository is not None:
            close_repository()
