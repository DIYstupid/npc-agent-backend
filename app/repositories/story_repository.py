import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.story import (
    StoryGraph,
    StoryGraphStatus,
    StoryPlayerProgress,
    StoryProgressStatus,
    StoryRecord,
    StoryValidationReport,
)


class StoryRepository:
    """SQLite repository for story documents, graphs, and player progress."""

    def __init__(self, db_path: str = "app/data/story.db") -> None:
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()

    def _ensure_db_dir(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_tables(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS story_documents (
                    story_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    rag_doc_id TEXT NOT NULL,
                    raw_markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS story_graphs (
                    story_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    graph_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    activated_at TEXT,
                    FOREIGN KEY (story_id) REFERENCES story_documents(story_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS story_player_progress (
                    story_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    current_stage_id TEXT NOT NULL,
                    completed_stage_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (story_id, player_id),
                    FOREIGN KEY (story_id) REFERENCES story_documents(story_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_story_graphs_status
                ON story_graphs (status, activated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_story_player_progress_player
                ON story_player_progress (player_id, status)
                """
            )
            conn.commit()

    def save_story(
        self,
        graph: StoryGraph,
        source: str,
        rag_doc_id: str,
        raw_markdown: str,
        validation: StoryValidationReport,
        status: StoryGraphStatus = "draft",
    ) -> StoryRecord:
        created_at = datetime.now(UTC).isoformat()
        title = graph.title

        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO story_documents (
                    story_id,
                    title,
                    source,
                    rag_doc_id,
                    raw_markdown,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(story_id) DO UPDATE SET
                    title = excluded.title,
                    source = excluded.source,
                    rag_doc_id = excluded.rag_doc_id,
                    raw_markdown = excluded.raw_markdown
                """,
                (
                    graph.story_id,
                    title,
                    source,
                    rag_doc_id,
                    raw_markdown,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO story_graphs (
                    story_id,
                    status,
                    graph_json,
                    validation_json,
                    activated_at
                )
                VALUES (?, ?, ?, ?, NULL)
                ON CONFLICT(story_id) DO UPDATE SET
                    status = excluded.status,
                    graph_json = excluded.graph_json,
                    validation_json = excluded.validation_json,
                    activated_at = CASE
                        WHEN excluded.status = 'active'
                        THEN story_graphs.activated_at
                        ELSE NULL
                    END
                """,
                (
                    graph.story_id,
                    status,
                    self._dump_model(graph),
                    self._dump_model(validation),
                ),
            )
            conn.commit()

        saved = self.get_story(graph.story_id)
        if saved is None:
            raise RuntimeError(f"Failed to save story: {graph.story_id}")
        return saved

    def get_story(self, story_id: str) -> StoryRecord | None:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                """
                SELECT
                    d.story_id,
                    d.title,
                    d.source,
                    d.rag_doc_id,
                    d.raw_markdown,
                    d.created_at,
                    g.graph_json,
                    g.validation_json,
                    g.status,
                    g.activated_at
                FROM story_documents d
                JOIN story_graphs g ON g.story_id = d.story_id
                WHERE d.story_id = ?
                """,
                (story_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return self._story_from_row(row)

    def activate_story(self, story_id: str) -> StoryRecord | None:
        activated_at = datetime.now(UTC).isoformat()
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                """
                UPDATE story_graphs
                SET status = 'active',
                    activated_at = ?
                WHERE story_id = ?
                """,
                (activated_at, story_id),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return None
        return self.get_story(story_id)

    def save_player_progress(
        self,
        progress: StoryPlayerProgress,
    ) -> StoryPlayerProgress:
        updated_at = datetime.now(UTC).isoformat()
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO story_player_progress (
                    story_id,
                    player_id,
                    current_stage_id,
                    completed_stage_ids_json,
                    status,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(story_id, player_id) DO UPDATE SET
                    current_stage_id = excluded.current_stage_id,
                    completed_stage_ids_json = excluded.completed_stage_ids_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    progress.story_id,
                    progress.player_id,
                    progress.current_stage_id,
                    json.dumps(progress.completed_stage_ids, ensure_ascii=False),
                    progress.status,
                    updated_at,
                ),
            )
            conn.commit()

        return progress

    def get_player_progress(
        self,
        story_id: str,
        player_id: str,
    ) -> StoryPlayerProgress | None:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                """
                SELECT
                    story_id,
                    player_id,
                    current_stage_id,
                    completed_stage_ids_json,
                    status
                FROM story_player_progress
                WHERE story_id = ?
                    AND player_id = ?
                """,
                (story_id, player_id),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return StoryPlayerProgress(
            story_id=str(row[0]),
            player_id=str(row[1]),
            current_stage_id=str(row[2]),
            completed_stage_ids=self._load_list(row[3]),
            status=self._progress_status(row[4]),
        )

    def _story_from_row(self, row: tuple[object, ...]) -> StoryRecord:
        graph = StoryGraph.model_validate(json.loads(str(row[6])))
        validation = StoryValidationReport.model_validate(json.loads(str(row[7])))
        return StoryRecord(
            story_id=str(row[0]),
            title=str(row[1]),
            source=str(row[2]),
            rag_doc_id=str(row[3]),
            raw_markdown=str(row[4]),
            created_at=str(row[5]),
            graph=graph,
            validation=validation,
            status=self._graph_status(row[8]),
            activated_at=str(row[9]) if row[9] is not None else None,
        )

    def _dump_model(self, value: object) -> str:
        if hasattr(value, "model_dump"):
            return json.dumps(
                value.model_dump(mode="json"),
                ensure_ascii=False,
            )
        return json.dumps(value, ensure_ascii=False)

    def _load_list(self, value: object) -> list[str]:
        try:
            loaded = json.loads(str(value))
        except json.JSONDecodeError:
            return []

        if not isinstance(loaded, list):
            return []
        return [str(item) for item in loaded if str(item)]

    def _graph_status(self, value: object) -> StoryGraphStatus:
        if value == "active":
            return "active"
        return "draft"

    def _progress_status(self, value: object) -> StoryProgressStatus:
        if value == "not_started":
            return "not_started"
        if value == "completed":
            return "completed"
        return "active"

    def close(self) -> None:
        pass
