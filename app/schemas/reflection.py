from pydantic import BaseModel, Field


class MemoryReflectionResult(BaseModel):
    """
    对一轮对话进行反思后的结果。

    should_remember:
      是否值得写入长期记忆。

    memory_text:
      要保存的长期记忆文本。

    memory_type:
      记忆分类，例如 profile、quest、relationship、world_event。

    importance:
      记忆重要性，1-5。
    """

    should_remember: bool = Field(
        default=False,
        description="这轮对话是否值得写入长期记忆",
    )
    memory_text: str | None = Field(
        default=None,
        description="要写入长期记忆的文本",
    )
    memory_type: str = Field(
        default="general",
        description="要写入长期记忆的类型",
    )
    importance: int = Field(
        default=1,
        ge=1,
        le=5,
        description="记忆重要性，1 到 5",
    )
