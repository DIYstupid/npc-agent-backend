import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.schemas.chat import AgentAction, ChatMessage
from app.schemas.context import ContextReport
from app.schemas.memory import LongTermMemory
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.tool import ToolExecutionResult
from app.schemas.trace import PromptTraceRecord, PromptTraceSummary


class TraceService:
    """Persists prompt traces for debugging and future Qt visualization."""

    def __init__(
        self,
        db_path: str | None = None,
        max_records: int | None = None,
    ) -> None:
        self.db_path = db_path or settings.TRACE_DB_PATH
        self.max_records = max_records or settings.TRACE_MAX_RECORDS
        self._ensure_db_dir()
        self._init_table()

    def _ensure_db_dir(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_traces (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    npc_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    estimated_prompt_tokens INTEGER NOT NULL,
                    estimated_saved_tokens INTEGER NOT NULL,
                    actions_count INTEGER NOT NULL,
                    executed_actions_count INTEGER NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    error TEXT,
                    record_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_chat_trace(
        self,
        request_id: str,
        npc_id: str,
        player_id: str,
        message: str,
        reply: str,
        prompt: str,
        context_report: ContextReport,
        actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
        selected_short_term_memory: list[ChatMessage],
        selected_long_term_memory: list[LongTermMemory],
        summary_memory: str,
        elapsed_ms: int,
        error: str | None = None,
        selected_shared_knowledge: list[KnowledgeEvent] | None = None,
    ) -> PromptTraceRecord:
        record = PromptTraceRecord(
            request_id=request_id,
            created_at=datetime.now(UTC).isoformat(),
            agent_type="chat",
            npc_id=npc_id,
            player_id=player_id,
            message=message,
            reply=reply,
            prompt=prompt,
            context_report=context_report,
            actions=actions,
            executed_actions=executed_actions,
            selected_short_term_memory=selected_short_term_memory,
            selected_long_term_memory=selected_long_term_memory,
            selected_shared_knowledge=selected_shared_knowledge or [],
            summary_memory=summary_memory,
            elapsed_ms=elapsed_ms,
            error=error,
        )

        self._save_record(record)
        return record

    def save_agent_trace(
        self,
        request_id: str,
        agent_type: str,
        player_id: str | None,
        message: str,
        reply: str,
        actions: list[AgentAction] | None = None,
        executed_actions: list[ToolExecutionResult] | None = None,
        elapsed_ms: int = 0,
        npc_id: str | None = None,
        prompt: str = "",
        agent_state: dict | None = None,
        error: str | None = None,
    ) -> PromptTraceRecord:
        context_report = ContextReport(
            request_id=request_id,
            token_budget=0,
            estimated_prompt_tokens=0,
            estimated_saved_tokens=0,
            section_tokens={
                "agent": 0,
            },
        )
        record = PromptTraceRecord(
            request_id=request_id,
            created_at=datetime.now(UTC).isoformat(),
            agent_type=agent_type,
            npc_id=npc_id or agent_type,
            player_id=player_id or "world",
            message=message,
            reply=reply,
            prompt=prompt,
            context_report=context_report,
            actions=actions or [],
            executed_actions=executed_actions or [],
            selected_short_term_memory=[],
            selected_long_term_memory=[],
            selected_shared_knowledge=[],
            summary_memory="",
            agent_state=agent_state or {},
            elapsed_ms=elapsed_ms,
            error=error,
        )

        self._save_record(record)
        return record

    def _save_record(self, record: PromptTraceRecord) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_traces (
                    request_id,
                    created_at,
                    npc_id,
                    player_id,
                    estimated_prompt_tokens,
                    estimated_saved_tokens,
                    actions_count,
                    executed_actions_count,
                    elapsed_ms,
                    error,
                    record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
                    record.created_at,
                    record.npc_id,
                    record.player_id,
                    record.context_report.estimated_prompt_tokens,
                    record.context_report.estimated_saved_tokens,
                    len(record.actions),
                    len(record.executed_actions),
                    record.elapsed_ms,
                    record.error,
                    self._record_to_json(record),
                ),
            )
            self._trim_old_records(conn)
            conn.commit()

    def list_traces(self, limit: int = 20) -> list[PromptTraceSummary]:
        limit = max(1, min(limit, 100))
        with closing(self._get_connection()) as conn:
            rows = conn.execute(
                """
                SELECT record_json
                FROM prompt_traces
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            self._record_to_summary(self._row_to_record(row))
            for row in rows
        ]

    def get_trace(self, request_id: str) -> PromptTraceRecord | None:
        with closing(self._get_connection()) as conn:
            row = conn.execute(
                """
                SELECT record_json
                FROM prompt_traces
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def latest_trace(self) -> PromptTraceRecord | None:
        with closing(self._get_connection()) as conn:
            row = conn.execute(
                """
                SELECT record_json
                FROM prompt_traces
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def _trim_old_records(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            DELETE FROM prompt_traces
            WHERE request_id NOT IN (
                SELECT request_id
                FROM prompt_traces
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (self.max_records,),
        )

    def _record_to_json(self, record: PromptTraceRecord) -> str:
        return json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
        )

    def _row_to_record(self, row: sqlite3.Row) -> PromptTraceRecord:
        return PromptTraceRecord.model_validate_json(row["record_json"])

    def _record_to_summary(
        self,
        record: PromptTraceRecord,
    ) -> PromptTraceSummary:
        return PromptTraceSummary(
            request_id=record.request_id,
            created_at=record.created_at,
            agent_type=record.agent_type,
            npc_id=record.npc_id,
            player_id=record.player_id,
            message_preview=record.message[:80],
            estimated_prompt_tokens=record.context_report.estimated_prompt_tokens,
            estimated_saved_tokens=record.context_report.estimated_saved_tokens,
            actions_count=len(record.actions),
            executed_actions_count=len(record.executed_actions),
            elapsed_ms=record.elapsed_ms,
            error=record.error,
        )

    def close(self) -> None:
        pass
