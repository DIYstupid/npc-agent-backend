from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.game import QuestObjective
from app.schemas.rag import SourceText
from app.schemas.tool import AgentAction
from app.schemas.validation import ResourceId


StoryImportStatus = Literal["valid", "needs_review", "invalid"]
StoryGraphStatus = Literal["draft", "active"]
StoryProgressStatus = Literal["not_started", "active", "completed"]
StoryValidationSeverity = Literal["error", "warning", "info"]


class StoryDocumentImportRequest(BaseModel):
    """Request body for importing a loose Markdown story document."""

    content: str = Field(..., min_length=1, max_length=200_000)
    source: SourceText = Field(..., description="Human-readable story source")
    title: str | None = Field(default=None, max_length=200)
    activate: bool = False
    player_id: ResourceId | None = None


class StoryValidationIssue(BaseModel):
    severity: StoryValidationSeverity
    path: str
    message: str
    suggestion: str | None = None


class StoryValidationReport(BaseModel):
    issues: list[StoryValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)


class StoryEntity(BaseModel):
    entity_id: ResourceId
    name: str = Field(..., min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    description: str | None = Field(default=None, max_length=1000)
    auto_generated: bool = False


class StoryEntities(BaseModel):
    npcs: list[StoryEntity] = Field(default_factory=list)
    locations: list[StoryEntity] = Field(default_factory=list)
    items: list[StoryEntity] = Field(default_factory=list)
    enemies: list[StoryEntity] = Field(default_factory=list)
    factions: list[StoryEntity] = Field(default_factory=list)


class StoryCondition(BaseModel):
    type: ResourceId
    key: ResourceId | None = None
    value: str | bool | int | float | None = None
    description: str | None = Field(default=None, max_length=500)


class StoryStage(BaseModel):
    stage_id: ResourceId
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    trigger_npc_id: ResourceId | None = None
    quest_id: ResourceId
    objectives: list[QuestObjective] = Field(default_factory=list, max_length=20)
    preconditions: list[StoryCondition] = Field(default_factory=list, max_length=20)
    completion_conditions: list[StoryCondition] = Field(
        default_factory=list,
        max_length=20,
    )
    next_stage_ids: list[ResourceId] = Field(default_factory=list, max_length=10)
    guidance: str = Field(default="", max_length=2000)
    allowed_npc_ids: list[ResourceId] = Field(default_factory=list, max_length=50)
    forbidden_spoilers: list[str] = Field(default_factory=list, max_length=20)
    reward_actions: list[AgentAction] = Field(default_factory=list, max_length=20)
    world_flag_updates: dict[str, bool] = Field(default_factory=dict, max_length=20)


class StoryGraph(BaseModel):
    story_id: ResourceId
    title: str = Field(..., min_length=1, max_length=200)
    world_summary: str = Field(default="", max_length=4000)
    entities: StoryEntities = Field(default_factory=StoryEntities)
    stages: list[StoryStage] = Field(default_factory=list, max_length=100)


class StoryPlayerProgress(BaseModel):
    story_id: ResourceId
    player_id: ResourceId
    current_stage_id: ResourceId
    completed_stage_ids: list[ResourceId] = Field(default_factory=list)
    status: StoryProgressStatus = "active"


class StoryDirective(BaseModel):
    story_id: ResourceId
    current_stage_id: ResourceId
    main_goal: str
    guidance: str
    trigger_npc_id: ResourceId | None = None
    can_current_npc_offer_quest: bool = False
    suggested_quest_id: ResourceId | None = None
    objectives: list[QuestObjective] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_spoilers: list[str] = Field(default_factory=list)
    relevant_lore_query: str = ""


class StoryImportPreview(BaseModel):
    story_id: ResourceId
    rag_doc_id: str
    candidate_graph: StoryGraph
    validation: StoryValidationReport
    status: StoryImportStatus


class StoryRecord(BaseModel):
    story_id: ResourceId
    title: str
    source: str
    rag_doc_id: str
    raw_markdown: str
    graph: StoryGraph
    validation: StoryValidationReport
    status: StoryGraphStatus
    created_at: str
    activated_at: str | None = None


class StoryActivationRequest(BaseModel):
    player_id: ResourceId | None = None


class StoryActivationResponse(BaseModel):
    story_id: ResourceId
    status: StoryGraphStatus
    progress: StoryPlayerProgress | None = None
