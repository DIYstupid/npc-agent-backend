import time
import uuid
from typing import TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.schemas.chat import AgentAction
from app.schemas.quest import QuestAgentRequest, QuestAgentResponse
from app.schemas.tool import ToolExecutionResult
from app.services.game_service import GameService
from app.services.tool_service import ToolService
from app.services.trace_service import TraceService


class QuestAgentState(TypedDict, total=False):
    request_id: str
    player_id: str
    quest_id: str
    operation: str
    note: str | None
    objectives: list[dict]
    actions: list[AgentAction]
    validated_actions: list[AgentAction]
    executed_actions: list[ToolExecutionResult]
    status: str
    message: str
    started_at: float
    elapsed_ms: int


class QuestAgent:
    """LangGraph-backed agent for quest lifecycle state transitions."""

    def __init__(
        self,
        tool_service: ToolService,
        game_service: GameService,
        trace_service: TraceService | None = None,
        checkpointer: object | None = None,
        checkpoint_db_path: str | None = None,
    ) -> None:
        self.tool_service = tool_service
        self.game_service = game_service
        self.trace_service = trace_service
        self.checkpointer = checkpointer
        self.checkpoint_db_path = checkpoint_db_path
        self.graph = None if checkpoint_db_path else self._build_graph(checkpointer=checkpointer)

    def _build_graph(self, checkpointer: object | None) -> object:
        graph = StateGraph(QuestAgentState)
        graph.add_node("plan_action", self._plan_action)
        graph.add_node("execute_action", self._execute_action)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "plan_action")
        graph.add_edge("plan_action", "execute_action")
        graph.add_edge("execute_action", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, request: QuestAgentRequest) -> QuestAgentResponse:
        request_id = f"quest_{uuid.uuid4().hex}"
        initial_state: QuestAgentState = {
            "request_id": request_id,
            "player_id": request.player_id,
            "quest_id": request.quest_id,
            "operation": self._normalize_operation(request.operation),
            "note": request.note,
            "objectives": [objective.model_dump(mode="json") for objective in request.objectives],
            "started_at": time.perf_counter(),
        }

        thread_id = f"quest:{request.player_id}:{request.quest_id}:{request_id}"
        result = await self._ainvoke_graph(initial_state, thread_id)

        player_state = self.game_service.get_player_state(request.player_id)
        return QuestAgentResponse(
            request_id=result["request_id"],
            player_id=result["player_id"],
            quest_id=result["quest_id"],
            operation=result["operation"],
            status=result["status"],
            message=result["message"],
            executed_actions=result.get("executed_actions", []),
            player_state=player_state,
        )

    async def _ainvoke_graph(
        self,
        initial_state: QuestAgentState,
        thread_id: str,
    ) -> QuestAgentState:
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

    async def _plan_action(self, state: QuestAgentState) -> QuestAgentState:
        operation = self._normalize_operation(state["operation"])
        quest_id = state["quest_id"]

        if operation in {"create", "advance"}:
            tool = "create_quest"
        elif operation == "complete":
            tool = "complete_quest"
        else:
            return {
                "operation": operation,
                "actions": [],
                "status": "invalid_operation",
                "message": f"Unsupported quest operation: {operation}",
            }

        args = {"quest_id": quest_id}
        if operation in {"create", "advance"}:
            args["objectives"] = state.get("objectives", [])

        return {
            "operation": operation,
            "actions": [
                AgentAction(
                    tool=tool,
                    args=args,
                )
            ],
        }

    async def _execute_action(self, state: QuestAgentState) -> QuestAgentState:
        actions = state.get("actions", [])
        if state.get("status") == "invalid_operation":
            return {
                "executed_actions": [],
            }

        action_execution = self.tool_service.execute_actions_with_validation(
            player_id=state["player_id"],
            actions=actions,
        )
        return {
            "validated_actions": action_execution.validated_actions,
            "executed_actions": action_execution.executed_actions,
        }

    async def _finalize(self, state: QuestAgentState) -> QuestAgentState:
        executed_actions = state.get("executed_actions", [])
        elapsed_ms = int((time.perf_counter() - state.get("started_at", time.perf_counter())) * 1000)

        if state.get("status") == "invalid_operation":
            status = "invalid_operation"
            message = state["message"]
        elif not executed_actions:
            status = "no_action"
            message = "No quest action executed"
        else:
            result = executed_actions[-1]
            status = str(result.data.get("status") or ("ok" if result.success else "failed"))
            message = result.message

        if self.trace_service is not None:
            self.trace_service.save_agent_trace(
                request_id=state["request_id"],
                agent_type="quest_agent",
                player_id=state["player_id"],
                message=f"{state['operation']} quest {state['quest_id']}",
                reply=message,
                actions=state.get("actions", []),
                validated_actions=state.get("validated_actions", []),
                executed_actions=executed_actions,
                elapsed_ms=elapsed_ms,
                agent_state={
                    "quest_id": state["quest_id"],
                    "operation": state["operation"],
                    "note": state.get("note"),
                    "objectives": state.get("objectives", []),
                    "status": status,
                },
            )

        return {
            "status": status,
            "message": message,
            "elapsed_ms": elapsed_ms,
        }

    def _normalize_operation(self, operation: str) -> str:
        normalized = (operation or "advance").strip().lower()
        if normalized == "start":
            return "create"
        if normalized == "finish":
            return "complete"
        return normalized
