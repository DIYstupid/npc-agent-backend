import inspect

from pydantic import ValidationError

from app.schemas.chat import AgentAction
from app.schemas.tool import (
    TOOL_ARGUMENT_MODELS,
    ToolExecutionBatch,
    ToolExecutionResult,
)
from app.services.game_service import GameService
from app.services.shared_knowledge_service import SharedKnowledgeService


class ToolService:
    """
    工具执行服务。

    负责执行 Agent 输出的结构化 actions。

    注意：
    LLM 不能直接修改游戏状态。
    所有 action 必须经过 ToolService 白名单校验后才能执行。
    """

    def __init__(
        self,
        game_service: GameService,
        shared_knowledge_service: SharedKnowledgeService | None = None,
    ) -> None:
        self.game_service = game_service
        self.shared_knowledge_service = shared_knowledge_service

        self.allowed_tools = set(TOOL_ARGUMENT_MODELS)

    def execute_actions(
        self,
        player_id: str,
        actions: list[AgentAction],
    ) -> list[ToolExecutionResult]:
        """
        执行多条 AgentAction。
        """

        return self.execute_actions_with_validation(
            player_id=player_id,
            actions=actions,
        ).executed_actions

    def execute_actions_with_validation(
        self,
        player_id: str,
        actions: list[AgentAction],
    ) -> ToolExecutionBatch:
        """Validate actions before applying any side effects."""

        validated_actions: list[AgentAction] = []
        executed_actions: list[ToolExecutionResult] = []

        for action in actions:
            validated_action, validation_error = self._validate_action(action)
            if validation_error is not None:
                executed_actions.append(validation_error)
                continue

            validated_actions.append(validated_action)
            executed_actions.append(
                self._execute_validated_action(
                    player_id=player_id,
                    action=validated_action,
                )
            )

        return ToolExecutionBatch(
            raw_actions=list(actions),
            validated_actions=validated_actions,
            executed_actions=executed_actions,
        )

    def execute_action(
        self,
        player_id: str,
        action: AgentAction,
    ) -> ToolExecutionResult:
        """
        执行单条 AgentAction。

        所有工具都必须在 allowed_tools 白名单里。
        """

        batch = self.execute_actions_with_validation(
            player_id=player_id,
            actions=[action],
        )
        return batch.executed_actions[0]

    def _execute_validated_action(
        self,
        player_id: str,
        action: AgentAction,
    ) -> ToolExecutionResult:
        if action.tool == "create_quest":
            return self._create_quest(player_id, action.args)

        if action.tool == "complete_quest":
            return self._complete_quest(player_id, action.args)

        if action.tool == "add_item":
            return self._add_item(player_id, action.args)

        if action.tool == "remove_item":
            return self._remove_item(player_id, action.args)

        if action.tool == "move_player":
            return self._move_player(player_id, action.args)

        if action.tool == "update_relationship":
            return self._update_relationship(player_id, action.args)

        if action.tool == "set_world_flag":
            return self._set_world_flag(player_id, action.args)

        if action.tool == "publish_knowledge":
            return self._publish_knowledge(player_id, action.args)

        if action.tool == "mark_knowledge_known":
            return self._mark_knowledge_known(action.args)

        if action.tool == "resolve_knowledge":
            return self._resolve_knowledge(action.args)

        return ToolExecutionResult(
            tool=action.tool,
            success=False,
            message=f"Tool not implemented: {action.tool}",
            data={"status": "invalid_action"},
        )

    def _validate_action(
        self,
        action: AgentAction,
    ) -> tuple[AgentAction, None] | tuple[None, ToolExecutionResult]:
        if action.tool not in self.allowed_tools:
            return None, ToolExecutionResult(
                tool=action.tool,
                success=False,
                message=f"Tool not allowed: {action.tool}",
                data={
                    "status": "not_allowed",
                    "allowed_tools": sorted(self.allowed_tools),
                },
            )

        args_model = TOOL_ARGUMENT_MODELS.get(action.tool)
        if args_model is None:
            return None, ToolExecutionResult(
                tool=action.tool,
                success=False,
                message=f"Tool schema not implemented: {action.tool}",
                data={"status": "invalid_action"},
            )

        try:
            validated_args = args_model.model_validate(action.args)
        except ValidationError as exc:
            return None, ToolExecutionResult(
                tool=action.tool,
                success=False,
                message=f"Invalid tool arguments: {action.tool}",
                data={
                    "status": "invalid_action",
                    "errors": self._format_validation_errors(exc),
                },
            )

        return AgentAction(
            tool=action.tool,
            args=validated_args.model_dump(mode="json", exclude_none=True),
        ), None

    def _format_validation_errors(self, exc: ValidationError) -> list[dict]:
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )
        return errors

    def _create_quest(self, player_id: str, args: dict) -> ToolExecutionResult:
        quest_id = args.get("quest_id")

        if not quest_id:
            return ToolExecutionResult(
                tool="create_quest",
                success=False,
                message="Missing required argument: quest_id",
                data={"status": "invalid_args"},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="create_quest",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "quest_id": quest_id},
            )

        objectives = args.get("objectives")
        if quest_id in player.active_quests:
            if objectives:
                self._create_quest_in_game_service(
                    player_id=player_id,
                    quest_id=quest_id,
                    objectives=objectives,
                )
            return ToolExecutionResult(
                tool="create_quest",
                success=True,
                message=f"Quest already active: {quest_id}",
                data={
                    "status": "already_active",
                    "quest_id": quest_id,
                    "objectives_updated": bool(objectives),
                },
            )

        if quest_id in player.completed_quests:
            return ToolExecutionResult(
                tool="create_quest",
                success=True,
                message=f"Quest already completed: {quest_id}",
                data={"status": "already_completed", "quest_id": quest_id},
            )

        success = self._create_quest_in_game_service(
            player_id=player_id,
            quest_id=quest_id,
            objectives=objectives,
        )

        return ToolExecutionResult(
            tool="create_quest",
            success=success,
            message=f"Quest created: {quest_id}" if success else "Failed to create quest",
            data={
                "status": "created" if success else "failed",
                "quest_id": quest_id,
            },
        )

    def _complete_quest(self, player_id: str, args: dict) -> ToolExecutionResult:
        quest_id = args.get("quest_id")

        if not quest_id:
            return ToolExecutionResult(
                tool="complete_quest",
                success=False,
                message="Missing required argument: quest_id",
                data={"status": "invalid_args"},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="complete_quest",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "quest_id": quest_id},
            )

        if quest_id in player.completed_quests:
            return ToolExecutionResult(
                tool="complete_quest",
                success=True,
                message=f"Quest already completed: {quest_id}",
                data={"status": "already_completed", "quest_id": quest_id},
            )

        if quest_id not in player.active_quests:
            return ToolExecutionResult(
                tool="complete_quest",
                success=False,
                message=f"Quest is not active: {quest_id}",
                data={"status": "not_active", "quest_id": quest_id},
            )

        progress = player.quest_progress.get(quest_id)
        if progress is not None and progress.objectives:
            remaining_objectives = [
                objective.objective_id
                for objective in progress.objectives
                if objective.status != "completed"
            ]
            if remaining_objectives:
                return ToolExecutionResult(
                    tool="complete_quest",
                    success=False,
                    message=f"Quest objectives incomplete: {quest_id}",
                    data={
                        "status": "objectives_incomplete",
                        "quest_id": quest_id,
                        "remaining_objectives": remaining_objectives,
                    },
                )

        success = self.game_service.complete_quest(
            player_id=player_id,
            quest_id=quest_id,
        )

        return ToolExecutionResult(
            tool="complete_quest",
            success=success,
            message=f"Quest completed: {quest_id}" if success else "Failed to complete quest",
            data={
                "status": "completed" if success else "failed",
                "quest_id": quest_id,
            },
        )

    def _add_item(self, player_id: str, args: dict) -> ToolExecutionResult:
        item_id = args.get("item_id")

        if not item_id:
            return ToolExecutionResult(
                tool="add_item",
                success=False,
                message="Missing required argument: item_id",
                data={"status": "invalid_args"},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="add_item",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "item_id": item_id},
            )

        if item_id in player.inventory:
            return ToolExecutionResult(
                tool="add_item",
                success=True,
                message=f"Item already exists: {item_id}",
                data={"status": "already_exists", "item_id": item_id},
            )

        success = self.game_service.add_item(
            player_id=player_id,
            item_id=item_id,
        )

        return ToolExecutionResult(
            tool="add_item",
            success=success,
            message=f"Item added: {item_id}" if success else "Failed to add item",
            data={
                "status": "added" if success else "failed",
                "item_id": item_id,
            },
        )

    def _remove_item(self, player_id: str, args: dict) -> ToolExecutionResult:
        item_id = args.get("item_id")

        if not item_id:
            return ToolExecutionResult(
                tool="remove_item",
                success=False,
                message="Missing required argument: item_id",
                data={"status": "invalid_args"},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="remove_item",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "item_id": item_id},
            )

        if item_id not in player.inventory:
            return ToolExecutionResult(
                tool="remove_item",
                success=False,
                message=f"Item not found: {item_id}",
                data={"status": "not_found", "item_id": item_id},
            )

        success = self.game_service.remove_item(
            player_id=player_id,
            item_id=item_id,
        )

        return ToolExecutionResult(
            tool="remove_item",
            success=success,
            message=f"Item removed: {item_id}" if success else f"Item not found: {item_id}",
            data={
                "status": "removed" if success else "failed",
                "item_id": item_id,
            },
        )

    def _move_player(self, player_id: str, args: dict) -> ToolExecutionResult:
        location = args.get("location")

        if not location:
            return ToolExecutionResult(
                tool="move_player",
                success=False,
                message="Missing required argument: location",
                data={"status": "invalid_args"},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="move_player",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "location": location},
            )

        previous_location = player.location
        if previous_location == location:
            return ToolExecutionResult(
                tool="move_player",
                success=True,
                message=f"Player already at location: {location}",
                data={
                    "status": "already_at_location",
                    "location": location,
                    "previous_location": previous_location,
                },
            )

        success = self.game_service.set_location(
            player_id=player_id,
            location=str(location),
        )

        return ToolExecutionResult(
            tool="move_player",
            success=success,
            message=f"Player moved to: {location}" if success else "Failed to move player",
            data={
                "status": "moved" if success else "failed",
                "location": location,
                "previous_location": previous_location,
            },
        )

    def _update_relationship(self, player_id: str, args: dict) -> ToolExecutionResult:
        npc_id = args.get("npc_id")
        delta = args.get("delta")

        if not npc_id:
            return ToolExecutionResult(
                tool="update_relationship",
                success=False,
                message="Missing required argument: npc_id",
                data={"status": "invalid_args"},
            )

        if delta is None:
            return ToolExecutionResult(
                tool="update_relationship",
                success=False,
                message="Missing required argument: delta",
                data={"status": "invalid_args", "npc_id": npc_id},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="update_relationship",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "npc_id": npc_id},
            )

        previous_value = player.relationships.get(npc_id, 0)
        delta = int(delta)
        success = self.game_service.update_relationship(
            player_id=player_id,
            npc_id=npc_id,
            delta=delta,
        )

        return ToolExecutionResult(
            tool="update_relationship",
            success=success,
            message=f"Relationship updated: {npc_id} {delta:+d}" if success else "Failed to update relationship",
            data={
                "status": "updated" if success else "failed",
                "npc_id": npc_id,
                "delta": delta,
                "previous_value": previous_value,
                "new_value": previous_value + delta if success else previous_value,
            },
        )

    def _set_world_flag(self, player_id: str, args: dict) -> ToolExecutionResult:
        flag = args.get("flag")
        value = args.get("value")

        if not flag:
            return ToolExecutionResult(
                tool="set_world_flag",
                success=False,
                message="Missing required argument: flag",
                data={"status": "invalid_args"},
            )

        if value is None:
            return ToolExecutionResult(
                tool="set_world_flag",
                success=False,
                message="Missing required argument: value",
                data={"status": "invalid_args", "flag": flag},
            )

        player = self.game_service.get_player_state(player_id)
        if player is None:
            return ToolExecutionResult(
                tool="set_world_flag",
                success=False,
                message=f"Player not found: {player_id}",
                data={"status": "player_not_found", "flag": flag},
            )

        value = bool(value)
        previous_value = player.world_flags.get(flag)
        if previous_value == value:
            return ToolExecutionResult(
                tool="set_world_flag",
                success=True,
                message=f"World flag already set: {flag}={value}",
                data={
                    "status": "already_set",
                    "flag": flag,
                    "value": value,
                    "previous_value": previous_value,
                },
            )

        success = self.game_service.set_world_flag(
            player_id=player_id,
            flag=flag,
            value=value,
        )

        return ToolExecutionResult(
            tool="set_world_flag",
            success=success,
            message=f"World flag set: {flag}={value}" if success else "Failed to set world flag",
            data={
                "status": "set" if success else "failed",
                "flag": flag,
                "value": value,
                "previous_value": previous_value,
            },
        )

    def _publish_knowledge(self, player_id: str, args: dict) -> ToolExecutionResult:
        if self.shared_knowledge_service is None:
            return ToolExecutionResult(
                tool="publish_knowledge",
                success=False,
                message="Shared knowledge service is unavailable",
                data={"status": "unavailable"},
            )

        text = args.get("text")
        if not text:
            return ToolExecutionResult(
                tool="publish_knowledge",
                success=False,
                message="Missing required argument: text",
                data={"status": "invalid_args"},
            )

        event = self.shared_knowledge_service.publish_event(
            text=str(text),
            player_id=str(args.get("player_id") or player_id),
            world_id=str(args.get("world_id") or "default"),
            scope=str(args.get("scope") or "player"),
            related_player_ids=self._as_string_list(args.get("related_player_ids")),
            source_npc_id=args.get("source_npc_id"),
            subject_npc_ids=self._as_string_list(args.get("subject_npc_ids")),
            known_by_npc_ids=self._as_string_list(args.get("known_by_npc_ids")),
            location=args.get("location"),
            event_type=str(args.get("event_type") or "general"),
            confidence=float(args.get("confidence", 1.0)),
            status=str(args.get("status") or "active"),
            expires_at=args.get("expires_at"),
            tags=self._as_string_list(args.get("tags")),
        )

        return ToolExecutionResult(
            tool="publish_knowledge",
            success=True,
            message=f"Knowledge published: {event.event_id}",
            data={
                "status": "published",
                "event_id": event.event_id,
                "scope": event.scope,
                "player_id": event.player_id,
                "known_by_npc_ids": event.known_by_npc_ids,
                "subject_npc_ids": event.subject_npc_ids,
            },
        )

    def _mark_knowledge_known(self, args: dict) -> ToolExecutionResult:
        if self.shared_knowledge_service is None:
            return ToolExecutionResult(
                tool="mark_knowledge_known",
                success=False,
                message="Shared knowledge service is unavailable",
                data={"status": "unavailable"},
            )

        event_id = args.get("event_id")
        npc_id = args.get("npc_id")
        if not event_id or not npc_id:
            return ToolExecutionResult(
                tool="mark_knowledge_known",
                success=False,
                message="Missing required argument: event_id or npc_id",
                data={"status": "invalid_args"},
            )

        event = self.shared_knowledge_service.mark_known_by(
            event_id=str(event_id),
            npc_id=str(npc_id),
        )
        if event is None:
            return ToolExecutionResult(
                tool="mark_knowledge_known",
                success=False,
                message=f"Knowledge event not found: {event_id}",
                data={"status": "not_found", "event_id": event_id},
            )

        return ToolExecutionResult(
            tool="mark_knowledge_known",
            success=True,
            message=f"Knowledge marked known by {npc_id}",
            data={
                "status": "known",
                "event_id": event.event_id,
                "npc_id": npc_id,
            },
        )

    def _resolve_knowledge(self, args: dict) -> ToolExecutionResult:
        if self.shared_knowledge_service is None:
            return ToolExecutionResult(
                tool="resolve_knowledge",
                success=False,
                message="Shared knowledge service is unavailable",
                data={"status": "unavailable"},
            )

        event_id = args.get("event_id")
        if not event_id:
            return ToolExecutionResult(
                tool="resolve_knowledge",
                success=False,
                message="Missing required argument: event_id",
                data={"status": "invalid_args"},
            )

        event = self.shared_knowledge_service.resolve_event(str(event_id))
        if event is None:
            return ToolExecutionResult(
                tool="resolve_knowledge",
                success=False,
                message=f"Knowledge event not found: {event_id}",
                data={"status": "not_found", "event_id": event_id},
            )

        return ToolExecutionResult(
            tool="resolve_knowledge",
            success=True,
            message=f"Knowledge resolved: {event.event_id}",
            data={
                "status": event.status,
                "event_id": event.event_id,
            },
        )

    def _as_string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        return [str(value)]

    def _create_quest_in_game_service(
        self,
        player_id: str,
        quest_id: str,
        objectives: list | None,
    ) -> bool:
        parameters = inspect.signature(self.game_service.create_quest).parameters
        if objectives is not None and "objectives" in parameters:
            return self.game_service.create_quest(
                player_id=player_id,
                quest_id=quest_id,
                objectives=objectives,
            )

        return self.game_service.create_quest(
            player_id=player_id,
            quest_id=quest_id,
        )
