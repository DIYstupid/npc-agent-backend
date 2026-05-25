from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from app.schemas.game import QuestObjective
from app.schemas.validation import MemoryText, ResourceId, Tag


ToolText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class AgentAction(BaseModel):
    """Structured action emitted by the NPC agent."""

    tool: str = Field(..., description="Tool name")
    args: dict[str, Any] = Field(
        default_factory=dict,
        max_length=20,
        description="Tool arguments",
    )


class BaseToolArgs(BaseModel):
    """Base class for validated tool arguments."""

    model_config = ConfigDict(extra="forbid")


class CreateQuestArgs(BaseToolArgs):
    quest_id: ResourceId
    objectives: list[QuestObjective] = Field(default_factory=list, max_length=20)


class CompleteQuestArgs(BaseToolArgs):
    quest_id: ResourceId


class AddItemArgs(BaseToolArgs):
    item_id: ResourceId


class RemoveItemArgs(BaseToolArgs):
    item_id: ResourceId


class MovePlayerArgs(BaseToolArgs):
    location: ToolText


class UpdateRelationshipArgs(BaseToolArgs):
    npc_id: ResourceId
    delta: int


class SetWorldFlagArgs(BaseToolArgs):
    flag: ResourceId
    value: bool


class PublishKnowledgeArgs(BaseToolArgs):
    text: MemoryText
    player_id: ResourceId | None = None
    world_id: ResourceId = "default"
    scope: ResourceId = "player"
    related_player_ids: list[ResourceId] = Field(default_factory=list, max_length=20)
    source_npc_id: ResourceId | None = None
    subject_npc_ids: list[ResourceId] = Field(default_factory=list, max_length=20)
    known_by_npc_ids: list[ResourceId] = Field(default_factory=list, max_length=50)
    location: ToolText | None = None
    event_type: ResourceId = "general"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: ResourceId = "active"
    expires_at: ToolText | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=20)


class MarkKnowledgeKnownArgs(BaseToolArgs):
    event_id: ResourceId
    npc_id: ResourceId


class ResolveKnowledgeArgs(BaseToolArgs):
    event_id: ResourceId


TOOL_ARGUMENT_MODELS: dict[str, type[BaseToolArgs]] = {
    "create_quest": CreateQuestArgs,
    "complete_quest": CompleteQuestArgs,
    "add_item": AddItemArgs,
    "remove_item": RemoveItemArgs,
    "move_player": MovePlayerArgs,
    "update_relationship": UpdateRelationshipArgs,
    "set_world_flag": SetWorldFlagArgs,
    "publish_knowledge": PublishKnowledgeArgs,
    "mark_knowledge_known": MarkKnowledgeKnownArgs,
    "resolve_knowledge": ResolveKnowledgeArgs,
}


class CreateQuestAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["create_quest"]
    args: CreateQuestArgs


class CompleteQuestAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["complete_quest"]
    args: CompleteQuestArgs


class AddItemAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["add_item"]
    args: AddItemArgs


class RemoveItemAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["remove_item"]
    args: RemoveItemArgs


class MovePlayerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["move_player"]
    args: MovePlayerArgs


class UpdateRelationshipAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["update_relationship"]
    args: UpdateRelationshipArgs


class SetWorldFlagAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["set_world_flag"]
    args: SetWorldFlagArgs


class PublishKnowledgeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["publish_knowledge"]
    args: PublishKnowledgeArgs


class MarkKnowledgeKnownAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["mark_knowledge_known"]
    args: MarkKnowledgeKnownArgs


class ResolveKnowledgeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["resolve_knowledge"]
    args: ResolveKnowledgeArgs


AgentActionContract = Annotated[
    CreateQuestAction
    | CompleteQuestAction
    | AddItemAction
    | RemoveItemAction
    | MovePlayerAction
    | UpdateRelationshipAction
    | SetWorldFlagAction
    | PublishKnowledgeAction
    | MarkKnowledgeKnownAction
    | ResolveKnowledgeAction,
    Field(discriminator="tool"),
]


def agent_action_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for the LLM-facing AgentAction contract."""

    return TypeAdapter(AgentActionContract).json_schema()


class ToolExecutionResult(BaseModel):
    """
    工具执行结果。

    每个 action 执行后，都会生成一个结果。
    """

    tool: str
    success: bool
    message: str
    data: dict = Field(default_factory=dict)


class ToolExecutionBatch(BaseModel):
    """Tool validation and execution details for prompt traces."""

    raw_actions: list[AgentAction] = Field(default_factory=list)
    validated_actions: list[AgentAction] = Field(default_factory=list)
    executed_actions: list[ToolExecutionResult] = Field(default_factory=list)
