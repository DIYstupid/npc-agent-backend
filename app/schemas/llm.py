from pydantic import BaseModel, Field

from app.schemas.chat import AgentAction


class LLMChatResult(BaseModel):
    """
    LLM 输出结果。

    reply:
      NPC 自然语言回复。

    actions:
      Agent 输出的结构化动作计划。
    """

    reply: str = Field(..., description="NPC 对玩家说的话")
    actions: list[AgentAction] = Field(default_factory=list)