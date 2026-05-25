from app.repositories.player_state_repository import PlayerStateRepository
from app.schemas.game import PlayerState, QuestObjective, QuestProgress


class GameService:
    """
    游戏状态服务。

    Day 6 更新：
    - 不再直接使用内存 dict 保存玩家状态
    - 改为通过 PlayerStateRepository 读写 SQLite
    """

    def __init__(self, player_state_repository: PlayerStateRepository) -> None:
        self.player_state_repository = player_state_repository

    def get_player_state(self, player_id: str) -> PlayerState | None:
        return self.player_state_repository.get_player_state(player_id)

    def save_player_state(self, player_state: PlayerState) -> None:
        self.player_state_repository.save_player_state(player_state)

    def create_quest(
        self,
        player_id: str,
        quest_id: str,
        objectives: list[QuestObjective | dict] | None = None,
    ) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        if quest_id not in player.active_quests and quest_id not in player.completed_quests:
            player.active_quests.append(quest_id)

        if objectives is not None:
            player.quest_progress[quest_id] = QuestProgress(
                quest_id=quest_id,
                objectives=[self._normalize_objective(objective) for objective in objectives],
            )
        elif quest_id not in player.quest_progress:
            player.quest_progress[quest_id] = QuestProgress(quest_id=quest_id)

        self.save_player_state(player)
        return True

    def complete_quest(self, player_id: str, quest_id: str) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        if quest_id in player.active_quests:
            player.active_quests.remove(quest_id)

        if quest_id not in player.completed_quests:
            player.completed_quests.append(quest_id)

        if quest_id in player.quest_progress:
            progress = player.quest_progress[quest_id]
            progress.status = "completed"
            for objective in progress.objectives:
                objective.status = "completed"

        self.save_player_state(player)
        return True

    def set_location(self, player_id: str, location: str) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        player.location = location
        self.save_player_state(player)
        return True

    def add_item(self, player_id: str, item_id: str) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        player.inventory.append(item_id)

        self.save_player_state(player)
        return True

    def remove_item(self, player_id: str, item_id: str) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        if item_id not in player.inventory:
            return False

        player.inventory.remove(item_id)

        self.save_player_state(player)
        return True

    def update_relationship(self, player_id: str, npc_id: str, delta: int) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        current_value = player.relationships.get(npc_id, 0)
        player.relationships[npc_id] = current_value + delta

        self.save_player_state(player)
        return True

    def set_world_flag(self, player_id: str, flag: str, value: bool) -> bool:
        player = self.get_player_state(player_id)
        if player is None:
            return False

        player.world_flags[flag] = value

        self.save_player_state(player)
        return True

    def _normalize_objective(self, objective: QuestObjective | dict) -> QuestObjective:
        if isinstance(objective, QuestObjective):
            return objective
        return QuestObjective(**objective)

    def close(self) -> None:
        close_repository = getattr(self.player_state_repository, "close", None)
        if close_repository is not None:
            close_repository()
