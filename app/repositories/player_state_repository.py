import json
import sqlite3
from contextlib import closing
from typing import Any
from pathlib import Path

from app.data.seed import PLAYERS
from app.schemas.game import PlayerState


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


class PlayerStateRepository:
    """
    玩家状态持久化仓库。

    使用 SQLite 保存 PlayerState。

    当前为了简单，把复杂字段用 JSON 字符串保存：
    - inventory
    - active_quests
    - completed_quests
    - world_flags
    - relationships
    """

    def __init__(self, db_path: str = "app/data/npc_agent.db") -> None:
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_table()
        self._seed_initial_players()

    def _ensure_db_dir(self) -> None:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_table(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS player_states (
                    player_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    inventory TEXT NOT NULL,
                    active_quests TEXT NOT NULL,
                    completed_quests TEXT NOT NULL,
                    quest_progress TEXT NOT NULL DEFAULT '{}',
                    world_flags TEXT NOT NULL,
                    relationships TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(player_states)").fetchall()
            }
            if "quest_progress" not in columns:
                conn.execute(
                    """
                    ALTER TABLE player_states
                    ADD COLUMN quest_progress TEXT NOT NULL DEFAULT '{}'
                    """
                )
            conn.commit()

    def _seed_initial_players(self) -> None:
        """
        如果数据库里没有玩家，则从 seed.py 写入初始玩家数据。

        注意：
        这里只在玩家不存在时插入。
        不会覆盖已经保存过的玩家状态。
        """

        for player in PLAYERS:
            existing_player = self.get_player_state(player.player_id)
            if existing_player is None:
                self.save_player_state(player)

    def get_player_state(self, player_id: str) -> PlayerState | None:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                """
                SELECT
                    player_id,
                    name,
                    location,
                    inventory,
                    active_quests,
                    completed_quests,
                    quest_progress,
                    world_flags,
                    relationships
                FROM player_states
                WHERE player_id = ?
                """,
                (player_id,),
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return PlayerState(
            player_id=row[0],
            name=row[1],
            location=row[2],
            inventory=json.loads(row[3]),
            active_quests=json.loads(row[4]),
            completed_quests=json.loads(row[5]),
            quest_progress=json.loads(row[6]),
            world_flags=json.loads(row[7]),
            relationships=json.loads(row[8]),
        )

    def save_player_state(self, player_state: PlayerState) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute(
                """
                INSERT INTO player_states (
                    player_id,
                    name,
                    location,
                    inventory,
                    active_quests,
                    completed_quests,
                    quest_progress,
                    world_flags,
                    relationships
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    name = excluded.name,
                    location = excluded.location,
                    inventory = excluded.inventory,
                    active_quests = excluded.active_quests,
                    completed_quests = excluded.completed_quests,
                    quest_progress = excluded.quest_progress,
                    world_flags = excluded.world_flags,
                    relationships = excluded.relationships
                """,
                (
                    player_state.player_id,
                    player_state.name,
                    player_state.location,
                    json.dumps(player_state.inventory, ensure_ascii=False),
                    json.dumps(player_state.active_quests, ensure_ascii=False),
                    json.dumps(player_state.completed_quests, ensure_ascii=False),
                    json.dumps(_to_jsonable(player_state.quest_progress), ensure_ascii=False),
                    json.dumps(player_state.world_flags, ensure_ascii=False),
                    json.dumps(player_state.relationships, ensure_ascii=False),
                ),
            )
            conn.commit()

    def close(self) -> None:
        pass
