import time
import uuid
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.schemas.chat import AgentAction
from app.schemas.game import PlayerState, QuestObjective
from app.schemas.shared_knowledge import KnowledgeEvent
from app.schemas.tool import ToolExecutionResult
from app.schemas.world import (
    WorldActionRequest,
    WorldActionResponse,
    WorldAgentResponse,
    WorldEventCreate,
    WorldInteractionRequest,
    WorldInteractionResponse,
)
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService

if TYPE_CHECKING:
    from app.services.world_action_service import WorldActionService


class WorldAgentState(TypedDict, total=False):
    request_id: str
    world_id: str
    player_id: str | None
    text: str
    scope: str
    source_npc_id: str | None
    subject_npc_ids: list[str]
    known_by_npc_ids: list[str]
    location: str | None
    event_type: str
    confidence: float
    tags: list[str]
    world_flags: dict[str, bool]
    actions: list[AgentAction]
    executed_actions: list[ToolExecutionResult]
    event: KnowledgeEvent | None
    status: str
    message: str
    started_at: float
    elapsed_ms: int


class WorldAgent:
    """LangGraph-backed agent for world event publication and player world interactions."""

    _ACTION_VERBS = {
        "move": ["go", "went", "travel", "move", "visit", "reach", "arrive", "去", "前往", "到", "到达", "抵达", "走到"],
        "pick_item": ["pick", "collect", "gather", "take", "find", "obtain", "拿", "捡", "采集", "收集", "找到", "获得"],
        "use_item": ["use", "consume", "使用", "用掉", "使用了"],
        "submit_item_to_npc": ["submit", "deliver", "give", "hand", "return", "交给", "递给", "交付", "带给", "归还", "上交"],
        "talk_to_npc": ["talk", "speak", "report", "tell", "ask", "汇报", "报告", "告诉", "交谈", "对话", "询问"],
        "inspect_object": ["inspect", "investigate", "look", "search", "check", "examine", "调查", "检查", "查看", "搜索", "侦察", "观察"],
        "defeat_enemy": ["defeat", "kill", "fight", "slay", "击败", "打败", "消灭", "杀死", "击杀"],
    }

    _ENTITY_ALIASES = {
        "north_road": ["north road", "北路", "北边道路", "北方道路", "村外", "村外道路"],
        "wolf_tracks": ["wolf tracks", "wolf track", "wolves tracks", "狼踪", "狼群踪迹", "狼群足迹", "足迹", "踪迹", "痕迹"],
        "guard_001": ["guard", "guard captain", "captain", "守卫", "卫兵", "守卫队长", "队长"],
        "healer_001": ["healer", "药师", "治疗师", "医师"],
        "blacksmith_001": ["blacksmith", "smith", "铁匠"],
        "healing_herb": ["healing herb", "herb", "草药", "药草", "治疗草药"],
        "silver_ore": ["silver ore", "ore", "银矿", "银矿石"],
    }

    def __init__(
        self,
        shared_knowledge_service: SharedKnowledgeService,
        tool_service: ToolService,
        trace_service: TraceService | None = None,
        checkpointer: object | None = None,
        checkpoint_db_path: str | None = None,
    ) -> None:
        self.shared_knowledge_service = shared_knowledge_service
        self.tool_service = tool_service
        self.trace_service = trace_service
        self.checkpointer = checkpointer
        self.checkpoint_db_path = checkpoint_db_path
        self.world_action_service: WorldActionService | None = None
        self.graph = None if checkpoint_db_path else self._build_graph(checkpointer=checkpointer)

    def set_world_action_service(self, world_action_service: "WorldActionService") -> None:
        self.world_action_service = world_action_service

    def _build_graph(self, checkpointer: object | None) -> object:
        graph = StateGraph(WorldAgentState)
        graph.add_node("publish_event", self._publish_event)
        graph.add_node("apply_world_flags", self._apply_world_flags)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "publish_event")
        graph.add_edge("publish_event", "apply_world_flags")
        graph.add_edge("apply_world_flags", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, request: WorldEventCreate | WorldInteractionRequest) -> WorldAgentResponse | WorldInteractionResponse:
        if isinstance(request, WorldInteractionRequest):
            return await self.interact(request)

        request_id = f"world_{uuid.uuid4().hex}"
        initial_state: WorldAgentState = {
            "request_id": request_id,
            "world_id": request.world_id,
            "player_id": request.player_id,
            "text": request.text,
            "scope": request.scope,
            "source_npc_id": request.source_npc_id,
            "subject_npc_ids": request.subject_npc_ids,
            "known_by_npc_ids": request.known_by_npc_ids,
            "location": request.location,
            "event_type": request.event_type,
            "confidence": request.confidence,
            "tags": request.tags,
            "world_flags": request.world_flags,
            "started_at": time.perf_counter(),
        }

        thread_id = f"world:{request.world_id}:{request.player_id or 'global'}:{request_id}"
        result = await self._ainvoke_graph(initial_state, thread_id)

        return WorldAgentResponse(
            request_id=result["request_id"],
            world_id=result["world_id"],
            player_id=result.get("player_id"),
            status=result["status"],
            message=result["message"],
            event=result.get("event"),
            executed_actions=result.get("executed_actions", []),
        )

    async def interact(self, request: WorldInteractionRequest) -> WorldInteractionResponse:
        """Parse natural language into verifiable world actions, then record the result."""

        request_id = f"world_interaction_{uuid.uuid4().hex}"
        started_at = time.perf_counter()
        world_action_service = self.world_action_service
        if world_action_service is None:
            event_response = await self._record_unparsed_interaction(request)
            return WorldInteractionResponse(
                request_id=request_id,
                world_id=request.world_id,
                player_id=request.player_id,
                status="recorded",
                message="World interaction recorded; action execution service is unavailable.",
                events=[event_response.event] if event_response.event is not None else [],
            )

        player = world_action_service.game_service.get_player_state(request.player_id)
        if player is None:
            return WorldInteractionResponse(
                request_id=request_id,
                world_id=request.world_id,
                player_id=request.player_id,
                status="player_not_found",
                message=f"Player not found: {request.player_id}",
            )

        parsed_actions = self._parse_interaction_actions(request=request, player=player)
        if not parsed_actions:
            event_response = await self._record_unparsed_interaction(request)
            final_player = world_action_service.game_service.get_player_state(request.player_id)
            response = WorldInteractionResponse(
                request_id=request_id,
                world_id=request.world_id,
                player_id=request.player_id,
                status="recorded",
                message="World interaction recorded; no verifiable quest or state action was parsed.",
                events=[event_response.event] if event_response.event is not None else [],
                executed_actions=event_response.executed_actions,
                player_state=final_player,
            )
            self._save_interaction_trace(request, response, started_at)
            return response

        action_results: list[WorldActionResponse] = []
        for action in parsed_actions:
            action_results.append(await world_action_service.apply_action(action))

        events = [result.event for result in action_results if result.event is not None]
        executed_actions: list[ToolExecutionResult] = []
        quest_updates = []
        for result in action_results:
            executed_actions.extend(result.executed_actions)
            quest_updates.extend(result.quest_updates)

        final_player = world_action_service.game_service.get_player_state(request.player_id)
        response = WorldInteractionResponse(
            request_id=request_id,
            world_id=request.world_id,
            player_id=request.player_id,
            status=self._interaction_status(action_results),
            message=self._interaction_message(action_results),
            parsed_actions=parsed_actions,
            action_results=action_results,
            events=events,
            executed_actions=executed_actions,
            quest_updates=quest_updates,
            player_state=final_player,
        )
        self._save_interaction_trace(request, response, started_at)
        return response

    async def _ainvoke_graph(
        self,
        initial_state: WorldAgentState,
        thread_id: str,
    ) -> WorldAgentState:
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        if self.checkpoint_db_path:
            async with AsyncSqliteSaver.from_conn_string(self.checkpoint_db_path) as checkpointer:
                graph = self._build_graph(checkpointer=checkpointer)
                return await graph.ainvoke(initial_state, config=config)

        return await self.graph.ainvoke(initial_state, config=config)

    async def _record_unparsed_interaction(self, request: WorldInteractionRequest) -> WorldAgentResponse:
        response = await self.ainvoke(
            WorldEventCreate(
                text=request.text,
                player_id=request.player_id,
                world_id=request.world_id,
                scope="player",
                source_npc_id=request.npc_id,
                subject_npc_ids=[request.npc_id] if request.npc_id else [],
                known_by_npc_ids=[request.npc_id] if request.npc_id else [],
                location=request.location,
                event_type="world_interaction",
                confidence=0.6,
                tags=["world_interaction", "unparsed"],
            )
        )
        return response

    def _parse_interaction_actions(
        self,
        request: WorldInteractionRequest,
        player: PlayerState,
    ) -> list[WorldActionRequest]:
        actions: list[WorldActionRequest] = []
        seen: set[str] = set()

        for quest_id in player.active_quests:
            progress = player.quest_progress.get(quest_id)
            if progress is None:
                continue

            for objective in progress.objectives:
                if objective.status == "completed":
                    continue
                action = self._action_for_objective(request, objective)
                if action is None:
                    continue
                key = self._action_key(action)
                if key in seen:
                    continue
                seen.add(key)
                actions.append(action)

        for action in self._direct_actions(request, player):
            key = self._action_key(action)
            if key not in seen:
                seen.add(key)
                actions.append(action)

        return actions

    def _action_for_objective(
        self,
        request: WorldInteractionRequest,
        objective: QuestObjective,
    ) -> WorldActionRequest | None:
        objective_type = self._normalize(objective.type)

        if objective_type == "location_visited":
            if not objective.location or not self._mentions_action(request.text, "move", objective.location, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="move",
                location=objective.location,
                world_id=request.world_id,
                note=request.text,
            )

        if objective_type == "inventory_contains":
            if not objective.item_id or not self._mentions_action(request.text, "pick_item", objective.item_id, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="pick_item",
                target_id=objective.item_id,
                location=objective.location or request.location,
                world_id=request.world_id,
                payload={"quantity": objective.quantity},
                note=request.text,
            )

        if objective_type == "submit_item_to_npc":
            npc_id = objective.npc_id or request.npc_id
            if not objective.item_id or not npc_id:
                return None
            if not self._mentions_action(request.text, "submit_item_to_npc", objective.item_id, objective.description):
                return None
            if objective.npc_id and not self._mentions_entity_or_selected(request, objective.npc_id, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="submit_item_to_npc",
                npc_id=npc_id,
                location=objective.location or request.location,
                world_id=request.world_id,
                payload={"item_id": objective.item_id, "quantity": objective.quantity},
                note=request.text,
            )

        if objective_type == "talk_to_npc":
            npc_id = objective.npc_id or request.npc_id
            if not npc_id:
                return None
            if not self._mentions_action(request.text, "talk_to_npc", npc_id, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="talk_to_npc",
                npc_id=npc_id,
                location=objective.location or request.location,
                world_id=request.world_id,
                note=request.text,
            )

        if objective_type == "inspect_object":
            if not objective.target_id or not self._mentions_action(request.text, "inspect_object", objective.target_id, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="inspect_object",
                target_id=objective.target_id,
                location=objective.location or request.location,
                world_id=request.world_id,
                note=request.text,
            )

        if objective_type == "defeat_enemy":
            if not objective.target_id or not self._mentions_action(request.text, "defeat_enemy", objective.target_id, objective.description):
                return None
            return WorldActionRequest(
                player_id=request.player_id,
                action_type="defeat_enemy",
                target_id=objective.target_id,
                location=objective.location or request.location,
                world_id=request.world_id,
                note=request.text,
            )

        return None

    def _direct_actions(
        self,
        request: WorldInteractionRequest,
        player: PlayerState,
    ) -> list[WorldActionRequest]:
        actions: list[WorldActionRequest] = []
        if request.npc_id and self._contains_any(request.text, self._ACTION_VERBS["talk_to_npc"]):
            actions.append(
                WorldActionRequest(
                    player_id=request.player_id,
                    action_type="talk_to_npc",
                    npc_id=request.npc_id,
                    location=request.location,
                    world_id=request.world_id,
                    note=request.text,
                )
            )

        for item_id in player.inventory:
            if self._mentions_action(request.text, "use_item", item_id, None):
                actions.append(
                    WorldActionRequest(
                        player_id=request.player_id,
                        action_type="use_item",
                        target_id=item_id,
                        location=request.location,
                        world_id=request.world_id,
                        note=request.text,
                    )
                )

        return actions

    def _mentions_action(
        self,
        text: str,
        action_type: str,
        entity_id: str,
        description: str | None,
    ) -> bool:
        return self._contains_any(text, self._ACTION_VERBS[action_type]) and self._mentions_entity(
            text=text,
            entity_id=entity_id,
            description=description,
        )

    def _mentions_entity_or_selected(
        self,
        request: WorldInteractionRequest,
        entity_id: str,
        description: str | None,
    ) -> bool:
        if request.npc_id == entity_id:
            return True
        return self._mentions_entity(request.text, entity_id, description)

    def _mentions_entity(self, text: str, entity_id: str, description: str | None) -> bool:
        return self._contains_any(text, self._terms_for_entity(entity_id, description))

    def _terms_for_entity(self, entity_id: str, description: str | None) -> list[str]:
        terms = [entity_id, entity_id.replace("_", " ")]
        terms.extend(part for part in entity_id.split("_") if len(part) >= 3 and not part.isdigit())
        terms.extend(self._ENTITY_ALIASES.get(entity_id, []))
        if description:
            terms.append(description)
            terms.extend(term for term in description.replace(".", " ").split() if len(term) >= 4)
        return terms

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        normalized_text = self._normalize(text)
        for term in terms:
            normalized_term = self._normalize(term)
            if normalized_term and normalized_term in normalized_text:
                return True
        return False

    def _normalize(self, text: Any) -> str:
        return str(text or "").strip().lower().replace("-", "_")

    def _action_key(self, action: WorldActionRequest) -> str:
        payload = self._model_dump(action.payload)
        return "|".join(
            [
                action.action_type,
                action.target_id or "",
                action.npc_id or "",
                action.location or "",
                str(payload),
            ]
        )

    def _interaction_status(self, action_results: list[WorldActionResponse]) -> str:
        if not action_results:
            return "recorded"
        applied = [result for result in action_results if result.status == "applied"]
        if len(applied) == len(action_results):
            return "applied"
        if applied:
            return "partially_applied"
        return "rejected"

    def _interaction_message(self, action_results: list[WorldActionResponse]) -> str:
        if not action_results:
            return "World interaction recorded."
        completed = [
            update.quest_id
            for result in action_results
            for update in result.quest_updates
            if update.status == "completed"
        ]
        advanced = [
            update.quest_id
            for result in action_results
            for update in result.quest_updates
            if update.status != "completed"
        ]
        if completed:
            return f"World interaction applied; quests completed: {', '.join(completed)}"
        if advanced:
            return f"World interaction applied; quests advanced: {', '.join(advanced)}"
        if self._interaction_status(action_results) == "rejected":
            return "; ".join(result.message for result in action_results)
        return f"World interaction applied; actions: {len(action_results)}"

    def _save_interaction_trace(
        self,
        request: WorldInteractionRequest,
        response: WorldInteractionResponse,
        started_at: float,
    ) -> None:
        if self.trace_service is None:
            return

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        self.trace_service.save_agent_trace(
            request_id=response.request_id,
            agent_type="world_agent",
            player_id=request.player_id,
            message=request.text,
            reply=response.message,
            actions=[
                AgentAction(tool="world_action", args=self._model_dump(action))
                for action in response.parsed_actions
            ],
            executed_actions=response.executed_actions,
            elapsed_ms=elapsed_ms,
            agent_state={
                "world_id": request.world_id,
                "status": response.status,
                "parsed_actions": [self._model_dump(action) for action in response.parsed_actions],
                "quest_updates": [self._model_dump(update) for update in response.quest_updates],
                "event_ids": [event.event_id for event in response.events],
            },
        )

    def _model_dump(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "dict"):
            return value.dict()
        return value

    async def _publish_event(self, state: WorldAgentState) -> WorldAgentState:
        event = self.shared_knowledge_service.publish_event(
            text=state["text"],
            player_id=state.get("player_id"),
            world_id=state.get("world_id") or "default",
            scope=state.get("scope") or "world",
            source_npc_id=state.get("source_npc_id"),
            subject_npc_ids=state.get("subject_npc_ids", []),
            known_by_npc_ids=state.get("known_by_npc_ids", []),
            location=state.get("location"),
            event_type=state.get("event_type") or "world_event",
            confidence=state.get("confidence", 1.0),
            tags=state.get("tags", []),
        )
        return {
            "event": event,
        }

    async def _apply_world_flags(self, state: WorldAgentState) -> WorldAgentState:
        player_id = state.get("player_id")
        flags = state.get("world_flags", {})
        if not player_id or not flags:
            return {
                "actions": [],
                "executed_actions": [],
            }

        actions = [
            AgentAction(
                tool="set_world_flag",
                args={
                    "flag": flag,
                    "value": value,
                },
            )
            for flag, value in flags.items()
        ]
        executed_actions = self.tool_service.execute_actions(
            player_id=player_id,
            actions=actions,
        )
        return {
            "actions": actions,
            "executed_actions": executed_actions,
        }

    async def _finalize(self, state: WorldAgentState) -> WorldAgentState:
        event = state.get("event")
        executed_actions = state.get("executed_actions", [])
        elapsed_ms = int((time.perf_counter() - state.get("started_at", time.perf_counter())) * 1000)

        status = "published" if event is not None else "failed"
        if event is None:
            message = "World event was not published"
        elif executed_actions:
            message = f"World event published: {event.event_id}; flags updated: {len(executed_actions)}"
        else:
            message = f"World event published: {event.event_id}"

        if self.trace_service is not None:
            self.trace_service.save_agent_trace(
                request_id=state["request_id"],
                agent_type="world_agent",
                player_id=state.get("player_id"),
                message=state["text"],
                reply=message,
                actions=state.get("actions", []),
                executed_actions=executed_actions,
                elapsed_ms=elapsed_ms,
                agent_state={
                    "world_id": state["world_id"],
                    "event_id": event.event_id if event is not None else None,
                    "scope": state.get("scope"),
                    "event_type": state.get("event_type"),
                    "world_flags": state.get("world_flags", {}),
                    "status": status,
                },
            )

        return {
            "status": status,
            "message": message,
            "elapsed_ms": elapsed_ms,
        }
