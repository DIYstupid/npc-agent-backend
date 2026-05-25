import time
import uuid
from typing import Any

from app.agents.world_agent import WorldAgent
from app.schemas.chat import AgentAction
from app.schemas.game import PlayerState, QuestObjective, QuestProgressUpdate
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.tool import ToolExecutionResult
from app.schemas.world import WorldActionRequest, WorldActionResponse, WorldEventCreate
from app.services.game_service import GameService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


class WorldActionService:
    """Applies player/world interactions and advances verifiable quest objectives."""

    def __init__(
        self,
        game_service: GameService,
        tool_service: ToolService,
        world_agent: WorldAgent,
        trace_service: TraceService | None = None,
    ) -> None:
        self.game_service = game_service
        self.tool_service = tool_service
        self.world_agent = world_agent
        self.trace_service = trace_service

    async def apply_action(self, request: WorldActionRequest) -> WorldActionResponse:
        request_id = f"world_action_{uuid.uuid4().hex}"
        started_at = time.perf_counter()
        action_type = self._normalize_action_type(request.action_type)
        player = self.game_service.get_player_state(request.player_id)
        if player is None:
            return WorldActionResponse(
                request_id=request_id,
                player_id=request.player_id,
                action_type=action_type,
                status="player_not_found",
                message=f"Player not found: {request.player_id}",
            )

        planned_actions, precondition_failure = self._planned_tool_actions(
            request=request,
            action_type=action_type,
            player=player,
        )
        if precondition_failure is not None:
            executed_actions = [precondition_failure]
            action_success = False
        else:
            executed_actions = self.tool_service.execute_actions(
                player_id=request.player_id,
                actions=planned_actions,
            )
            action_success = all(result.success for result in executed_actions) if executed_actions else True

        world_response = await self.world_agent.ainvoke(
            self._world_event_request(
                request=request,
                action_type=action_type,
                action_success=action_success,
            )
        )
        event = world_response.event

        quest_updates: list[QuestProgressUpdate] = []
        quest_actions: list[ToolExecutionResult] = []
        if action_success:
            quest_updates, quest_actions = self._advance_quest_progress(
                request=request,
                action_type=action_type,
                event=event,
            )
            executed_actions.extend(quest_actions)

        final_player = self.game_service.get_player_state(request.player_id)
        status = "applied" if action_success else "rejected"
        message = self._response_message(
            request=request,
            action_type=action_type,
            action_success=action_success,
            executed_actions=executed_actions,
            quest_updates=quest_updates,
        )

        if self.trace_service is not None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            self.trace_service.save_agent_trace(
                request_id=request_id,
                agent_type="world_action",
                player_id=request.player_id,
                message=f"{action_type} {request.target_id or request.npc_id or request.location or ''}".strip(),
                reply=message,
                actions=planned_actions,
                executed_actions=executed_actions,
                elapsed_ms=elapsed_ms,
                agent_state={
                    "action_type": action_type,
                    "target_id": request.target_id,
                    "npc_id": request.npc_id,
                    "location": request.location,
                    "event_id": event.event_id if event is not None else None,
                    "quest_updates": [update.model_dump(mode="json") for update in quest_updates],
                    "status": status,
                },
            )

        return WorldActionResponse(
            request_id=request_id,
            player_id=request.player_id,
            action_type=action_type,
            status=status,
            message=message,
            event=event,
            executed_actions=executed_actions,
            quest_updates=quest_updates,
            player_state=final_player,
        )

    def _planned_tool_actions(
        self,
        request: WorldActionRequest,
        action_type: str,
        player: PlayerState,
    ) -> tuple[list[AgentAction], ToolExecutionResult | None]:
        actions: list[AgentAction] = []
        payload = request.payload

        if action_type in {"visit_location", "move"}:
            location = self._string_payload(payload, "location") or request.location or request.target_id
            if not location:
                return [], self._invalid_action("visit_location requires location")
            actions.append(AgentAction(tool="move_player", args={"location": location}))

        elif action_type in {"pick_item", "collect_item"}:
            item_id = self._string_payload(payload, "item_id") or request.target_id
            if not item_id:
                return [], self._invalid_action("pick_item requires item_id or target_id")
            actions.append(AgentAction(tool="add_item", args={"item_id": item_id}))

        elif action_type == "use_item":
            item_id = self._string_payload(payload, "item_id") or request.target_id
            if not item_id:
                return [], self._invalid_action("use_item requires item_id or target_id")
            if item_id not in player.inventory:
                return [], self._invalid_action(f"Item not found: {item_id}", status="item_not_found")
            if bool(payload.get("consume", True)):
                actions.append(AgentAction(tool="remove_item", args={"item_id": item_id}))

        elif action_type == "submit_item_to_npc":
            item_id = self._string_payload(payload, "item_id")
            npc_id = request.npc_id or request.target_id or self._string_payload(payload, "npc_id")
            if not item_id or not npc_id:
                return [], self._invalid_action("submit_item_to_npc requires item_id and npc_id")
            quantity = self._quantity(payload)
            if player.inventory.count(item_id) < quantity:
                return [], self._invalid_action(f"Required item not found: {item_id}", status="item_not_found")
            for _ in range(quantity):
                actions.append(AgentAction(tool="remove_item", args={"item_id": item_id}))

        elif action_type == "defeat_enemy":
            target_id = request.target_id or self._string_payload(payload, "enemy_id")
            if not target_id:
                return [], self._invalid_action("defeat_enemy requires target_id or enemy_id")
            flag = self._string_payload(payload, "flag") or f"defeated_{target_id}"
            actions.append(AgentAction(tool="set_world_flag", args={"flag": flag, "value": True}))

        elif action_type in {"talk_to_npc", "inspect_object"}:
            pass

        else:
            return [], self._invalid_action(f"Unsupported world action: {action_type}", status="unsupported_action")

        actions.extend(self._world_flag_actions(payload))
        return actions, None

    def _world_flag_actions(self, payload: dict[str, Any]) -> list[AgentAction]:
        actions: list[AgentAction] = []
        flags = payload.get("world_flags")
        if isinstance(flags, dict):
            for flag, value in flags.items():
                if str(flag):
                    actions.append(
                        AgentAction(
                            tool="set_world_flag",
                            args={"flag": str(flag), "value": bool(value)},
                        )
                    )

        flag = payload.get("flag")
        if flag:
            actions.append(
                AgentAction(
                    tool="set_world_flag",
                    args={"flag": str(flag), "value": bool(payload.get("value", True))},
                )
            )
        return actions

    def _world_event_request(
        self,
        request: WorldActionRequest,
        action_type: str,
        action_success: bool,
    ) -> WorldEventCreate:
        tags = ["world_action", action_type, "success" if action_success else "failed"]
        npc_id = request.npc_id or (
            request.target_id if action_type in {"talk_to_npc", "submit_item_to_npc"} else None
        )
        event_location = request.location
        if event_location is None:
            player = self.game_service.get_player_state(request.player_id)
            event_location = player.location if player is not None else None

        return WorldEventCreate(
            text=self._event_text(request, action_type, action_success),
            player_id=request.player_id,
            world_id=request.world_id,
            scope="player",
            subject_npc_ids=[npc_id] if npc_id else [],
            known_by_npc_ids=[npc_id] if npc_id else [],
            location=event_location,
            event_type=action_type,
            confidence=1.0 if action_success else 0.5,
            tags=tags,
        )

    def _advance_quest_progress(
        self,
        request: WorldActionRequest,
        action_type: str,
        event: KnowledgeEvent | None,
    ) -> tuple[list[QuestProgressUpdate], list[ToolExecutionResult]]:
        player = self.game_service.get_player_state(request.player_id)
        if player is None:
            return [], []

        updates: list[QuestProgressUpdate] = []
        completion_actions: list[ToolExecutionResult] = []

        for quest_id in list(player.active_quests):
            progress = player.quest_progress.get(quest_id)
            if progress is None or not progress.objectives:
                continue

            completed_now: list[str] = []
            for objective in progress.objectives:
                if objective.status == "completed":
                    continue
                if self._objective_met(
                    objective=objective,
                    request=request,
                    action_type=action_type,
                    player=player,
                    event=event,
                ):
                    objective.status = "completed"
                    completed_now.append(objective.objective_id)

            if not completed_now:
                continue

            remaining = [
                objective.objective_id
                for objective in progress.objectives
                if objective.status != "completed"
            ]
            if remaining:
                self.game_service.save_player_state(player)
                updates.append(
                    QuestProgressUpdate(
                        quest_id=quest_id,
                        status="advanced",
                        completed_objectives=completed_now,
                        remaining_objectives=remaining,
                        message=f"Quest advanced: {quest_id}",
                    )
                )
                continue

            self.game_service.save_player_state(player)
            completion_result = self.tool_service.execute_action(
                player_id=request.player_id,
                action=AgentAction(tool="complete_quest", args={"quest_id": quest_id}),
            )
            completion_actions.append(completion_result)
            updates.append(
                QuestProgressUpdate(
                    quest_id=quest_id,
                    status="completed" if completion_result.success else "advanced",
                    completed_objectives=completed_now,
                    remaining_objectives=[],
                    message=completion_result.message,
                )
            )
            player = self.game_service.get_player_state(request.player_id) or player

        return updates, completion_actions

    def _objective_met(
        self,
        objective: QuestObjective,
        request: WorldActionRequest,
        action_type: str,
        player: PlayerState,
        event: KnowledgeEvent | None,
    ) -> bool:
        objective_type = self._normalize_action_type(objective.type)

        if objective_type == "inventory_contains":
            return bool(objective.item_id) and player.inventory.count(objective.item_id) >= objective.quantity

        if objective_type == "location_visited":
            return bool(objective.location) and player.location == objective.location

        if objective_type == "world_flag":
            if not objective.flag:
                return False
            expected_value = True if objective.value is None else objective.value
            return player.world_flags.get(objective.flag) == expected_value

        if objective_type == "submit_item_to_npc":
            return (
                action_type == "submit_item_to_npc"
                and self._matches_optional(objective.item_id, self._string_payload(request.payload, "item_id"))
                and self._matches_optional(objective.npc_id, request.npc_id or request.target_id)
            )

        if objective_type == "talk_to_npc":
            return (
                action_type == "talk_to_npc"
                and self._matches_optional(objective.npc_id, request.npc_id or request.target_id)
            )

        if objective_type == "inspect_object":
            return (
                action_type == "inspect_object"
                and self._matches_optional(objective.target_id, request.target_id)
            )

        if objective_type == "defeat_enemy":
            return (
                action_type == "defeat_enemy"
                and self._matches_optional(objective.target_id, request.target_id)
            )

        if objective_type == "event_recorded":
            return event is not None and self._matches_optional(objective.event_type, event.event_type)

        return False

    def _event_text(
        self,
        request: WorldActionRequest,
        action_type: str,
        action_success: bool,
    ) -> str:
        if request.note:
            return request.note

        target = request.target_id or request.npc_id or request.location or self._string_payload(request.payload, "item_id")
        result = "succeeded" if action_success else "failed"
        if target:
            return f"Player {request.player_id} {result} at {action_type}: {target}."
        return f"Player {request.player_id} {result} at {action_type}."

    def _response_message(
        self,
        request: WorldActionRequest,
        action_type: str,
        action_success: bool,
        executed_actions: list[ToolExecutionResult],
        quest_updates: list[QuestProgressUpdate],
    ) -> str:
        if not action_success:
            failed = next((result for result in executed_actions if not result.success), None)
            return failed.message if failed is not None else f"World action rejected: {action_type}"

        if quest_updates:
            completed = [update.quest_id for update in quest_updates if update.status == "completed"]
            if completed:
                return f"World action applied; quests completed: {', '.join(completed)}"
            return f"World action applied; quests advanced: {', '.join(update.quest_id for update in quest_updates)}"

        return f"World action applied: {action_type}"

    def _invalid_action(self, message: str, status: str = "invalid_action") -> ToolExecutionResult:
        return ToolExecutionResult(
            tool="world_action",
            success=False,
            message=message,
            data={"status": status},
        )

    def _quantity(self, payload: dict[str, Any]) -> int:
        try:
            return max(1, int(payload.get("quantity", 1)))
        except (TypeError, ValueError):
            return 1

    def _string_payload(self, payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _matches_optional(self, expected: str | None, actual: str | None) -> bool:
        if expected is None:
            return True
        return expected == actual

    def _normalize_action_type(self, action_type: str) -> str:
        return (action_type or "").strip().lower()
