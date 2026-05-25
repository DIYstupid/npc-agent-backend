from typing import Any

from pydantic import BaseModel, Field


class QuestObjective(BaseModel):
    """A backend-verifiable quest objective."""

    objective_id: str
    type: str
    description: str | None = None
    status: str = "active"
    item_id: str | None = None
    quantity: int = Field(default=1, ge=1)
    npc_id: str | None = None
    location: str | None = None
    target_id: str | None = None
    flag: str | None = None
    value: Any = None
    event_type: str | None = None


class QuestProgress(BaseModel):
    """Per-player progress for a quest and its objectives."""

    quest_id: str
    status: str = "active"
    objectives: list[QuestObjective] = Field(default_factory=list)


class QuestProgressUpdate(BaseModel):
    """Quest progress changes caused by a world action."""

    quest_id: str
    status: str
    completed_objectives: list[str] = Field(default_factory=list)
    remaining_objectives: list[str] = Field(default_factory=list)
    message: str


class PlayerState(BaseModel):
    """
    玩家当前游戏状态。

    Day 5 新增：
    - relationships：玩家与 NPC 的关系值
    """

    player_id: str
    name: str
    location: str
    inventory: list[str] = Field(default_factory=list)
    active_quests: list[str] = Field(default_factory=list)
    completed_quests: list[str] = Field(default_factory=list)
    quest_progress: dict[str, QuestProgress] = Field(default_factory=dict)
    world_flags: dict = Field(default_factory=dict)
    relationships: dict[str, int] = Field(default_factory=dict)


class Location(BaseModel):
    """
    地图地点。
    """

    location_id: str
    name: str
    description: str


class Quest(BaseModel):
    """
    任务信息。
    """

    quest_id: str
    title: str
    description: str
    status: str = "inactive"
