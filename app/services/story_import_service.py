import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.repositories.story_repository import StoryRepository
from app.schemas.game import QuestObjective
from app.schemas.story import (
    StoryActivationResponse,
    StoryEntity,
    StoryEntities,
    StoryGraph,
    StoryImportPreview,
    StoryImportStatus,
    StoryPlayerProgress,
    StoryStage,
    StoryValidationIssue,
    StoryValidationReport,
)
from app.schemas.tool import TOOL_ARGUMENT_MODELS
from app.services.rag_knowledge_service import RagKnowledgeService


SUPPORTED_OBJECTIVE_TYPES = {
    "inventory_contains",
    "location_visited",
    "world_flag",
    "submit_item_to_npc",
    "talk_to_npc",
    "inspect_object",
    "defeat_enemy",
    "event_recorded",
}


class StoryActivationError(Exception):
    """Raised when a stored story cannot be activated safely."""

    def __init__(self, message: str, validation: StoryValidationReport) -> None:
        self.validation = validation
        super().__init__(message)


@dataclass
class MarkdownSection:
    heading: str | None
    body: str


class StoryMarkdownHeuristicParser:
    """Small deterministic parser for obvious Markdown story outlines."""

    _generic_targets = {
        "monster",
        "monsters",
        "enemy",
        "enemies",
        "foe",
        "foes",
        "boss",
        "final boss",
    }

    def parse(
        self,
        content: str,
        source: str,
        title: str | None = None,
    ) -> StoryGraph:
        story_id = self._story_id(source=source, content=content)
        resolved_title = title or self._first_heading(content) or self._title_from_source(source)
        sections = self._sections(content)
        world_summary = self._world_summary(sections=sections, content=content)
        main_story_text = self._main_story_text(sections=sections, content=content)
        stage_texts = self._stage_texts(main_story_text)
        entities = self._entities(content)

        stages: list[StoryStage] = []
        for index, stage_text in enumerate(stage_texts, start=1):
            stage_id = f"stage_{index:03d}"
            objectives = self._objectives_for_stage(
                stage_text=stage_text,
                index=index,
                entities=entities,
            )
            next_stage_ids = (
                [f"stage_{index + 1:03d}"] if index < len(stage_texts) else []
            )
            stages.append(
                StoryStage(
                    stage_id=stage_id,
                    title=self._stage_title(stage_text, index),
                    summary=stage_text,
                    quest_id=f"main_story_{index:03d}",
                    objectives=objectives,
                    next_stage_ids=next_stage_ids,
                    guidance=stage_text,
                )
            )

        return StoryGraph(
            story_id=story_id,
            title=resolved_title,
            world_summary=world_summary,
            entities=entities,
            stages=stages,
        )

    def _story_id(self, source: str, content: str) -> str:
        digest = hashlib.sha256(f"{source}\n{content}".encode("utf-8")).hexdigest()
        return f"story_{digest[:16]}"

    def _first_heading(self, content: str) -> str | None:
        for line in content.splitlines():
            match = re.match(r"^\s*#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()
        return None

    def _title_from_source(self, source: str) -> str:
        name = Path(source).stem.strip()
        return name or "Imported Story"

    def _sections(self, content: str) -> list[MarkdownSection]:
        sections: list[MarkdownSection] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in content.replace("\r\n", "\n").replace("\r", "\n").splitlines():
            match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
            if match:
                if current_lines or current_heading is not None:
                    sections.append(
                        MarkdownSection(
                            heading=current_heading,
                            body="\n".join(current_lines).strip(),
                        )
                    )
                current_heading = match.group(1).strip()
                current_lines = []
                continue
            current_lines.append(line)

        if current_lines or current_heading is not None:
            sections.append(
                MarkdownSection(
                    heading=current_heading,
                    body="\n".join(current_lines).strip(),
                )
            )

        return sections or [MarkdownSection(heading=None, body=content.strip())]

    def _world_summary(
        self,
        sections: list[MarkdownSection],
        content: str,
    ) -> str:
        world_sections = [
            section.body
            for section in sections
            if section.heading and self._is_world_heading(section.heading)
        ]
        if not world_sections:
            first_section = sections[0].body if sections else content
            world_sections = [first_section]
        return self._clean_markdown_text("\n\n".join(world_sections))[:4000]

    def _main_story_text(
        self,
        sections: list[MarkdownSection],
        content: str,
    ) -> str:
        main_sections = [
            section.body
            for section in sections
            if section.heading and self._is_main_story_heading(section.heading)
        ]
        if main_sections:
            return "\n\n".join(main_sections)

        non_world_sections = [
            section.body
            for section in sections
            if not section.heading or not self._is_world_heading(section.heading)
        ]
        if non_world_sections:
            return "\n\n".join(non_world_sections).strip()
        if any(section.heading for section in sections):
            return ""
        return content.strip()

    def _is_world_heading(self, heading: str) -> bool:
        normalized = heading.strip().lower()
        return any(
            marker in normalized
            for marker in ("world", "lore", "setting", "background", "世界", "背景")
        )

    def _is_main_story_heading(self, heading: str) -> bool:
        normalized = heading.strip().lower()
        return any(
            marker in normalized
            for marker in ("main story", "storyline", "main plot", "plot", "主线", "剧情")
        )

    def _stage_texts(self, main_story_text: str) -> list[str]:
        list_items = self._markdown_list_items(main_story_text)
        if list_items:
            return list_items

        compact_text = self._clean_markdown_text(main_story_text)
        if not compact_text:
            return []

        pieces = re.split(
            r"(?:[.!?;。！？；]\s*|,\s+(?:and\s+)?|，|、|\band then\b|\bthen\b|\band finally\b|\bfinally\b)",
            compact_text,
            flags=re.IGNORECASE,
        )
        stages = [self._strip_stage_prefix(piece) for piece in pieces]
        return [stage for stage in stages if stage]

    def _markdown_list_items(self, text: str) -> list[str]:
        items: list[str] = []
        for line in text.splitlines():
            match = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$", line)
            if match:
                item = self._clean_markdown_text(match.group(1))
                if item:
                    items.append(item)
        return items

    def _strip_stage_prefix(self, text: str) -> str:
        value = text.strip()
        value = re.sub(r"^(?:and|then|finally|and finally)\s+", "", value, flags=re.I)
        return value.strip(" -:\t")

    def _clean_markdown_text(self, text: str) -> str:
        value = re.sub(r"`([^`]+)`", r"\1", text)
        value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
        value = re.sub(r"\*([^*]+)\*", r"\1", value)
        value = re.sub(r"^\s*#{1,6}\s+", "", value, flags=re.MULTILINE)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _entities(self, content: str) -> StoryEntities:
        factions: list[StoryEntity] = []
        for name in self._capitalized_entities(content):
            if name.endswith(("Sect", "Valley", "Fort", "Guild", "Order", "Clan")):
                factions.append(
                    self._entity(
                        prefix="faction",
                        name=name,
                        description=None,
                        auto_generated=False,
                    )
                )
        return StoryEntities(factions=self._unique_entities(factions))

    def _capitalized_entities(self, content: str) -> list[str]:
        candidates = re.findall(
            r"\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3}\b",
            content,
        )
        ignored = {"World", "Main Story", "Story", "The"}
        return [candidate for candidate in candidates if candidate not in ignored]

    def _objectives_for_stage(
        self,
        stage_text: str,
        index: int,
        entities: StoryEntities,
    ) -> list[QuestObjective]:
        lower_text = stage_text.lower()
        defeat_target = self._defeat_target(stage_text)
        if defeat_target and defeat_target.lower() not in self._generic_targets:
            enemy = self._entity(
                prefix="enemy",
                name=defeat_target,
                description=f"Inferred from stage {index}: {stage_text}",
                auto_generated=True,
            )
            entities.enemies = self._unique_entities([*entities.enemies, enemy])
            return [
                QuestObjective(
                    objective_id=f"objective_{index:03d}_defeat",
                    type="defeat_enemy",
                    description=stage_text,
                    target_id=enemy.entity_id,
                )
            ]

        location = self._visit_location(stage_text)
        if location:
            entity = self._entity(
                prefix="location",
                name=location,
                description=f"Inferred from stage {index}: {stage_text}",
                auto_generated=True,
            )
            entities.locations = self._unique_entities([*entities.locations, entity])
            return [
                QuestObjective(
                    objective_id=f"objective_{index:03d}_visit",
                    type="location_visited",
                    description=stage_text,
                    location=location,
                )
            ]

        npc_name = self._talk_npc(stage_text)
        if npc_name:
            npc = self._entity(
                prefix="npc",
                name=npc_name,
                description=f"Inferred from stage {index}: {stage_text}",
                auto_generated=True,
            )
            entities.npcs = self._unique_entities([*entities.npcs, npc])
            return [
                QuestObjective(
                    objective_id=f"objective_{index:03d}_talk",
                    type="talk_to_npc",
                    description=stage_text,
                    npc_id=npc.entity_id,
                )
            ]

        if "fight monsters" in lower_text or "fight enemies" in lower_text:
            return []

        return []

    def _defeat_target(self, text: str) -> str | None:
        match = re.search(
            r"\b(?:defeat|defeats|defeated|kill|kills|slay|slays|clear|clears|fight|fights)\s+(?:the\s+)?(.+?)$",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        target = re.sub(r"\b(?:several|local|nearby|corrupt)\b", "", match.group(1), flags=re.I)
        target = re.sub(r"\s+", " ", target).strip(" .")
        return target or None

    def _visit_location(self, text: str) -> str | None:
        match = re.search(
            r"\b(?:start|starts|started|travel|travels|go|goes|reach|reaches|arrive|arrives)\s+(?:in|at|to)\s+(?:the\s+)?(.+?)$",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        location = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        return location or None

    def _talk_npc(self, text: str) -> str | None:
        match = re.search(
            r"\b(?:meet|meets|talk to|speak to|find)\s+(?:the\s+)?([A-Z][A-Za-z ]{2,80})$",
            text,
        )
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1)).strip(" .")

    def _stage_title(self, text: str, index: int) -> str:
        title = text.strip()
        if len(title) > 80:
            title = f"{title[:77].rstrip()}..."
        return title or f"Stage {index}"

    def _entity(
        self,
        prefix: str,
        name: str,
        description: str | None,
        auto_generated: bool,
    ) -> StoryEntity:
        return StoryEntity(
            entity_id=self._resource_id(prefix=prefix, text=name),
            name=name.strip(),
            aliases=[],
            description=description,
            auto_generated=auto_generated,
        )

    def _resource_id(self, prefix: str, text: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", text.lower())
        if words:
            slug = "_".join(words)[:48].strip("_")
        else:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            slug = digest[:16]
        return f"{prefix}_{slug}"[:64]

    def _unique_entities(self, entities: list[StoryEntity]) -> list[StoryEntity]:
        by_id: dict[str, StoryEntity] = {}
        for entity in entities:
            by_id[entity.entity_id] = entity
        return list(by_id.values())


class StoryValidationService:
    """Validates candidate story graphs before activation."""

    def validate(self, graph: StoryGraph) -> StoryValidationReport:
        issues: list[StoryValidationIssue] = []
        issues.extend(self._validate_stage_shape(graph))
        issues.extend(self._validate_stage_links(graph))
        issues.extend(self._validate_objectives(graph))
        issues.extend(self._validate_reward_actions(graph))
        return StoryValidationReport(issues=issues)

    def _validate_stage_shape(self, graph: StoryGraph) -> list[StoryValidationIssue]:
        issues: list[StoryValidationIssue] = []
        if not graph.stages:
            return [
                StoryValidationIssue(
                    severity="error",
                    path="stages",
                    message="Story graph must contain at least one stage.",
                    suggestion="Add a Main Story section or a numbered list of story stages.",
                )
            ]

        seen_stage_ids: set[str] = set()
        seen_quest_ids: set[str] = set()
        for index, stage in enumerate(graph.stages):
            path = f"stages[{index}]"
            if stage.stage_id in seen_stage_ids:
                issues.append(
                    StoryValidationIssue(
                        severity="error",
                        path=f"{path}.stage_id",
                        message=f"Duplicate stage_id: {stage.stage_id}",
                        suggestion="Use a unique stage_id for each stage.",
                    )
                )
            seen_stage_ids.add(stage.stage_id)

            if stage.quest_id in seen_quest_ids:
                issues.append(
                    StoryValidationIssue(
                        severity="error",
                        path=f"{path}.quest_id",
                        message=f"Duplicate quest_id: {stage.quest_id}",
                        suggestion="Use a unique quest_id for each main story stage.",
                    )
                )
            seen_quest_ids.add(stage.quest_id)

            if not stage.guidance.strip():
                issues.append(
                    StoryValidationIssue(
                        severity="error",
                        path=f"{path}.guidance",
                        message="Stage guidance is required.",
                        suggestion="Describe how NPCs should point players toward this stage.",
                    )
                )
            if not stage.objectives:
                issues.append(
                    StoryValidationIssue(
                        severity="warning",
                        path=f"{path}.objectives",
                        message="No verifiable objective was inferred; this stage is guidance-only.",
                        suggestion="Add a concrete objective such as talk_to_npc, location_visited, or defeat_enemy.",
                    )
                )

        return issues

    def _validate_stage_links(self, graph: StoryGraph) -> list[StoryValidationIssue]:
        issues: list[StoryValidationIssue] = []
        stage_ids = {stage.stage_id for stage in graph.stages}
        incoming_counts = {stage.stage_id: 0 for stage in graph.stages}

        for index, stage in enumerate(graph.stages):
            for next_stage_id in stage.next_stage_ids:
                if next_stage_id not in stage_ids:
                    issues.append(
                        StoryValidationIssue(
                            severity="error",
                            path=f"stages[{index}].next_stage_ids",
                            message=f"Unknown next_stage_id: {next_stage_id}",
                            suggestion="Point next_stage_ids only to existing stage IDs.",
                        )
                    )
                    continue
                incoming_counts[next_stage_id] += 1

        start_stage_ids = [
            stage_id for stage_id, count in incoming_counts.items() if count == 0
        ]
        if not start_stage_ids:
            issues.append(
                StoryValidationIssue(
                    severity="error",
                    path="stages",
                    message="Story graph has no start stage.",
                    suggestion="Remove accidental cycles or mark a clear first stage.",
                )
            )
        elif len(start_stage_ids) > 1:
            issues.append(
                StoryValidationIssue(
                    severity="warning",
                    path="stages",
                    message=f"Story graph has multiple start stages: {', '.join(start_stage_ids)}",
                    suggestion="Confirm whether this story should branch at the beginning.",
                )
            )

        cycle_path = self._find_cycle(graph)
        if cycle_path:
            issues.append(
                StoryValidationIssue(
                    severity="error",
                    path="stages.next_stage_ids",
                    message=f"Story graph contains a cycle: {' -> '.join(cycle_path)}",
                    suggestion="Remove the cycle for the MVP story graph.",
                )
            )

        return issues

    def _find_cycle(self, graph: StoryGraph) -> list[str]:
        next_by_stage = {
            stage.stage_id: list(stage.next_stage_ids)
            for stage in graph.stages
        }
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []

        def visit(stage_id: str) -> list[str]:
            if stage_id in visiting:
                if stage_id in stack:
                    return [*stack[stack.index(stage_id):], stage_id]
                return [stage_id]
            if stage_id in visited:
                return []

            visiting.add(stage_id)
            stack.append(stage_id)
            for next_stage_id in next_by_stage.get(stage_id, []):
                cycle = visit(next_stage_id)
                if cycle:
                    return cycle
            stack.pop()
            visiting.remove(stage_id)
            visited.add(stage_id)
            return []

        for stage_id in next_by_stage:
            cycle = visit(stage_id)
            if cycle:
                return cycle
        return []

    def _validate_objectives(self, graph: StoryGraph) -> list[StoryValidationIssue]:
        issues: list[StoryValidationIssue] = []
        for stage_index, stage in enumerate(graph.stages):
            for objective_index, objective in enumerate(stage.objectives):
                path = f"stages[{stage_index}].objectives[{objective_index}]"
                objective_type = objective.type.strip().lower()
                if objective_type not in SUPPORTED_OBJECTIVE_TYPES:
                    issues.append(
                        StoryValidationIssue(
                            severity="error",
                            path=f"{path}.type",
                            message=f"Unsupported objective type: {objective.type}",
                            suggestion=(
                                "Use one of: "
                                + ", ".join(sorted(SUPPORTED_OBJECTIVE_TYPES))
                            ),
                        )
                    )
                    continue

                missing_field = self._missing_required_objective_field(objective_type, objective)
                if missing_field is not None:
                    issues.append(
                        StoryValidationIssue(
                            severity="warning",
                            path=f"{path}.{missing_field}",
                            message=(
                                f"Objective type {objective_type} is missing "
                                f"required field {missing_field}."
                            ),
                            suggestion="Confirm or edit the generated objective before activation.",
                        )
                    )
        return issues

    def _missing_required_objective_field(
        self,
        objective_type: str,
        objective: QuestObjective,
    ) -> str | None:
        required_fields = {
            "inventory_contains": "item_id",
            "location_visited": "location",
            "world_flag": "flag",
            "submit_item_to_npc": "item_id",
            "talk_to_npc": "npc_id",
            "inspect_object": "target_id",
            "defeat_enemy": "target_id",
            "event_recorded": "event_type",
        }
        field = required_fields.get(objective_type)
        if field is None:
            return None
        if getattr(objective, field, None):
            return None
        return field

    def _validate_reward_actions(self, graph: StoryGraph) -> list[StoryValidationIssue]:
        issues: list[StoryValidationIssue] = []
        for stage_index, stage in enumerate(graph.stages):
            for action_index, action in enumerate(stage.reward_actions):
                path = f"stages[{stage_index}].reward_actions[{action_index}]"
                args_model = TOOL_ARGUMENT_MODELS.get(action.tool)
                if args_model is None:
                    issues.append(
                        StoryValidationIssue(
                            severity="error",
                            path=f"{path}.tool",
                            message=f"Reward action uses unsupported tool: {action.tool}",
                            suggestion="Use only tools whitelisted by ToolService.",
                        )
                    )
                    continue
                try:
                    args_model.model_validate(action.args)
                except ValidationError as exc:
                    issues.append(
                        StoryValidationIssue(
                            severity="error",
                            path=f"{path}.args",
                            message=f"Reward action arguments are invalid: {exc.errors()[0]['msg']}",
                            suggestion="Update reward action args to match the tool schema.",
                        )
                    )
        return issues


class StoryImportService:
    """Coordinates story Markdown import, RAG storage, validation, and activation."""

    def __init__(
        self,
        repository: StoryRepository,
        rag_knowledge_service: RagKnowledgeService,
        parser: StoryMarkdownHeuristicParser | None = None,
        validation_service: StoryValidationService | None = None,
    ) -> None:
        self.repository = repository
        self.rag_knowledge_service = rag_knowledge_service
        self.parser = parser or StoryMarkdownHeuristicParser()
        self.validation_service = validation_service or StoryValidationService()

    def import_story(
        self,
        content: str,
        source: str,
        title: str | None = None,
        activate: bool = False,
        player_id: str | None = None,
    ) -> StoryImportPreview:
        graph = self.parser.parse(
            content=content,
            source=source,
            title=title,
        )
        validation = self.validation_service.validate(graph)
        rag_response = self.rag_knowledge_service.import_document(
            content=content,
            source=source,
            doc_id=f"{graph.story_id}_source",
            title=title or graph.title,
            document_format="markdown",
            page=0,
            tags=[
                "story",
                "world_bible",
                "main_plot",
                f"story_id:{graph.story_id}",
            ],
        )
        self.repository.save_story(
            graph=graph,
            source=source,
            rag_doc_id=rag_response.doc_id,
            raw_markdown=content,
            validation=validation,
            status="draft",
        )

        if activate and not validation.has_errors:
            self.activate_story(story_id=graph.story_id, player_id=player_id)

        return StoryImportPreview(
            story_id=graph.story_id,
            rag_doc_id=rag_response.doc_id,
            candidate_graph=graph,
            validation=validation,
            status=self._preview_status(validation),
        )

    def get_story(self, story_id: str):
        return self.repository.get_story(story_id)

    def activate_story(
        self,
        story_id: str,
        player_id: str | None = None,
    ) -> StoryActivationResponse | None:
        record = self.repository.get_story(story_id)
        if record is None:
            return None

        if record.validation.has_errors:
            raise StoryActivationError(
                message="Story has validation errors and cannot be activated.",
                validation=record.validation,
            )

        activated = self.repository.activate_story(story_id)
        if activated is None:
            return None

        progress = None
        if player_id is not None:
            progress = self.activate_story_for_player(
                story_id=story_id,
                player_id=player_id,
            )

        return StoryActivationResponse(
            story_id=story_id,
            status="active",
            progress=progress,
        )

    def activate_story_for_player(
        self,
        story_id: str,
        player_id: str,
    ) -> StoryPlayerProgress:
        record = self.repository.get_story(story_id)
        if record is None:
            raise ValueError(f"Story not found: {story_id}")
        if record.validation.has_errors:
            raise StoryActivationError(
                message="Story has validation errors and cannot be activated.",
                validation=record.validation,
            )

        existing = self.repository.get_player_progress(
            story_id=story_id,
            player_id=player_id,
        )
        if existing is not None:
            return existing

        current_stage_id = self._start_stage_id(record.graph)
        progress = StoryPlayerProgress(
            story_id=story_id,
            player_id=player_id,
            current_stage_id=current_stage_id,
            completed_stage_ids=[],
            status="active",
        )
        return self.repository.save_player_progress(progress)

    def get_player_progress(
        self,
        story_id: str,
        player_id: str,
    ) -> StoryPlayerProgress | None:
        return self.repository.get_player_progress(
            story_id=story_id,
            player_id=player_id,
        )

    def _start_stage_id(self, graph: StoryGraph) -> str:
        if not graph.stages:
            raise ValueError(f"Story has no stages: {graph.story_id}")

        incoming_stage_ids = {
            next_stage_id
            for stage in graph.stages
            for next_stage_id in stage.next_stage_ids
        }
        for stage in graph.stages:
            if stage.stage_id not in incoming_stage_ids:
                return stage.stage_id
        return graph.stages[0].stage_id

    def _preview_status(
        self,
        validation: StoryValidationReport,
    ) -> StoryImportStatus:
        if validation.has_errors:
            return "invalid"
        if validation.has_warnings:
            return "needs_review"
        return "valid"
