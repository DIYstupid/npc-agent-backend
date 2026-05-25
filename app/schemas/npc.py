from pydantic import BaseModel, Field


class NPCProfile(BaseModel):
    """
    NPC 基础档案。

    这个模型描述一个 NPC 是谁、在哪里、有什么性格和目标。
    后续接入 LLM 时，这些字段会进入 Prompt，让模型按照 NPC 人设回复。
    """

    npc_id: str = Field(..., description="NPC 唯一 ID")
    name: str = Field(..., description="NPC 名字")
    role: str = Field(..., description="NPC 职业或身份")
    personality: str = Field(..., description="NPC 性格")
    faction: str = Field(..., description="NPC 所属阵营")
    goal: str = Field(..., description="NPC 当前目标")
    location: str = Field(..., description="NPC 当前所在地点")
    relationship: dict[str, int] = Field(
        default_factory=dict,
        description="NPC 对不同玩家的好感度，key 是 player_id，value 是分数"
    )