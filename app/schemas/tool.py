from pydantic import BaseModel, Field


class ToolExecutionResult(BaseModel):
    """
    工具执行结果。

    每个 action 执行后，都会生成一个结果。
    """

    tool: str
    success: bool
    message: str
    data: dict = Field(default_factory=dict)