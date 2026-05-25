import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.shared_knowledge import KnowledgeEvent


class SharedKnowledgeRepository:
    """SQLite repository for canonical cross-NPC knowledge events."""

    def __init__(self, db_path: str = "app/data/shared_knowledge.db") -> None:
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_table()

    def _ensure_db_dir(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_table(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_events (
                    event_id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    player_id TEXT,
                    related_player_ids TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_npc_id TEXT,
                    subject_npc_ids TEXT NOT NULL,
                    known_by_npc_ids TEXT NOT NULL,
                    location TEXT,
                    event_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    tags TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_events_lookup
                ON knowledge_events (world_id, player_id, status, event_type)
                """
            )
            conn.commit()

    def add_event(self, event: KnowledgeEvent) -> KnowledgeEvent:
        event = self._normalize_event(event)
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO knowledge_events (
                    event_id,
                    world_id,
                    scope,
                    player_id,
                    related_player_ids,
                    text,
                    source_npc_id,
                    subject_npc_ids,
                    known_by_npc_ids,
                    location,
                    event_type,
                    confidence,
                    status,
                    created_at,
                    expires_at,
                    tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row_values(event),
            )
            conn.commit()

        return event

    def get_event(self, event_id: str) -> KnowledgeEvent | None:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                """
                SELECT
                    event_id,
                    world_id,
                    scope,
                    player_id,
                    related_player_ids,
                    text,
                    source_npc_id,
                    subject_npc_ids,
                    known_by_npc_ids,
                    location,
                    event_type,
                    confidence,
                    status,
                    created_at,
                    expires_at,
                    tags
                FROM knowledge_events
                WHERE event_id = ?
                """,
                (event_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return self._from_row(row)

    def update_event(self, event: KnowledgeEvent) -> KnowledgeEvent:
        event = self._normalize_event(event)
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                UPDATE knowledge_events SET
                    world_id = ?,
                    scope = ?,
                    player_id = ?,
                    related_player_ids = ?,
                    text = ?,
                    source_npc_id = ?,
                    subject_npc_ids = ?,
                    known_by_npc_ids = ?,
                    location = ?,
                    event_type = ?,
                    confidence = ?,
                    status = ?,
                    created_at = ?,
                    expires_at = ?,
                    tags = ?
                WHERE event_id = ?
                """,
                (
                    event.world_id,
                    event.scope,
                    event.player_id,
                    json.dumps(event.related_player_ids, ensure_ascii=False),
                    event.text,
                    event.source_npc_id,
                    json.dumps(event.subject_npc_ids, ensure_ascii=False),
                    json.dumps(event.known_by_npc_ids, ensure_ascii=False),
                    event.location,
                    event.event_type,
                    event.confidence,
                    event.status,
                    event.created_at,
                    event.expires_at,
                    json.dumps(event.tags, ensure_ascii=False),
                    event.event_id,
                ),
            )
            conn.commit()

        return event

    def list_events(
        self,
        world_id: str = "default",
        player_id: str | None = None,
        npc_id: str | None = None,
        status: str | None = "active",
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        where_clauses = ["world_id = ?"]
        params: list[object] = [world_id]

        if status:
            where_clauses.append("status = ?")
            params.append(status)

        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)

        query = f"""
            SELECT
                event_id,
                world_id,
                scope,
                player_id,
                related_player_ids,
                text,
                source_npc_id,
                subject_npc_ids,
                known_by_npc_ids,
                location,
                event_type,
                confidence,
                status,
                created_at,
                expires_at,
                tags
            FROM knowledge_events
            WHERE {" AND ".join(where_clauses)}
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
        """
        params.append(max(1, limit))

        with closing(self._get_connection()) as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()

        events = [self._from_row(row) for row in rows]
        if player_id is not None:
            events = [
                event
                for event in events
                if self._matches_player_scope(event=event, player_id=player_id)
            ]
        if npc_id is not None:
            events = [
                event
                for event in events
                if self._matches_npc_visibility(event=event, npc_id=npc_id)
            ]

        return events

    def _to_row_values(self, event: KnowledgeEvent) -> tuple[object, ...]:
        return (
            event.event_id,
            event.world_id,
            event.scope,
            event.player_id,
            json.dumps(event.related_player_ids, ensure_ascii=False),
            event.text,
            event.source_npc_id,
            json.dumps(event.subject_npc_ids, ensure_ascii=False),
            json.dumps(event.known_by_npc_ids, ensure_ascii=False),
            event.location,
            event.event_type,
            event.confidence,
            event.status,
            event.created_at,
            event.expires_at,
            json.dumps(event.tags, ensure_ascii=False),
        )

    def _from_row(self, row: tuple[object, ...]) -> KnowledgeEvent:
        return KnowledgeEvent(
            event_id=str(row[0]),
            world_id=str(row[1]),
            scope=str(row[2]),
            player_id=str(row[3]) if row[3] is not None else None,
            related_player_ids=self._load_list(row[4]),
            text=str(row[5]),
            source_npc_id=str(row[6]) if row[6] is not None else None,
            subject_npc_ids=self._load_list(row[7]),
            known_by_npc_ids=self._load_list(row[8]),
            location=str(row[9]) if row[9] is not None else None,
            event_type=str(row[10]),
            confidence=float(row[11]),
            status=str(row[12]),
            created_at=str(row[13]) if row[13] is not None else None,
            expires_at=str(row[14]) if row[14] is not None else None,
            tags=self._load_list(row[15]),
        )

    def _normalize_event(self, event: KnowledgeEvent) -> KnowledgeEvent:
        created_at = event.created_at or datetime.now(UTC).isoformat()
        related_player_ids = self._unique_values(event.related_player_ids)
        if event.player_id and event.scope == "player":
            related_player_ids = self._unique_values([*related_player_ids, event.player_id])

        known_by_npc_ids = self._unique_values(event.known_by_npc_ids)
        if event.source_npc_id:
            known_by_npc_ids = self._unique_values([*known_by_npc_ids, event.source_npc_id])

        return event.model_copy(
            update={
                "world_id": event.world_id or "default",
                "scope": (event.scope or "player").strip(),
                "related_player_ids": related_player_ids,
                "subject_npc_ids": self._unique_values(event.subject_npc_ids),
                "known_by_npc_ids": known_by_npc_ids,
                "event_type": event.event_type or "general",
                "status": event.status or "active",
                "created_at": created_at,
                "tags": self._unique_values(event.tags),
            }
        )

    def _load_list(self, value: object) -> list[str]:
        if value is None:
            return []

        try:
            loaded = json.loads(str(value))
        except json.JSONDecodeError:
            return []

        if not isinstance(loaded, list):
            return []

        return [str(item) for item in loaded if str(item)]

    def _unique_values(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _matches_player_scope(self, event: KnowledgeEvent, player_id: str) -> bool:
        if event.scope == "world":
            return True
        if event.player_id == player_id:
            return True
        return player_id in event.related_player_ids

    def _matches_npc_visibility(self, event: KnowledgeEvent, npc_id: str) -> bool:
        return (
            npc_id == event.source_npc_id
            or npc_id in event.subject_npc_ids
            or npc_id in event.known_by_npc_ids
        )

    def close(self) -> None:
        pass
