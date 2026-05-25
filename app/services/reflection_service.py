from app.schemas.chat import AgentAction, ToolExecutionResult
from app.schemas.game import PlayerState
from app.schemas.npc import NPCProfile
from app.schemas.reflection import MemoryReflectionResult


class ReflectionService:
    """
    自动记忆沉淀服务。

    当前版本使用规则判断：
    - 玩家告诉名字
    - 创建任务
    - 完成任务
    - 关系值变化
    - 世界事件变化
    - 关键物品变化

    后续可以替换成 LLM Reflection。
    """

    def reflect(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        player_message: str,
        npc_reply: str,
        actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
    ) -> MemoryReflectionResult:
        name_memory = self._detect_player_name(
            npc=npc,
            player_message=player_message,
        )
        if name_memory:
            return name_memory

        action_memory = self._detect_action_memory(
            npc=npc,
            player_state=player_state,
            actions=actions,
            executed_actions=executed_actions,
        )
        if action_memory:
            return action_memory

        return MemoryReflectionResult(
            should_remember=False,
            memory_text=None,
            memory_type="general",
            importance=1,
        )

    def _detect_player_name(
        self,
        npc: NPCProfile,
        player_message: str,
    ) -> MemoryReflectionResult | None:
        if "我叫" not in player_message and "我的名字是" not in player_message:
            return None

        name = None

        if "我叫" in player_message:
            name = player_message.split("我叫", 1)[1]
        elif "我的名字是" in player_message:
            name = player_message.split("我的名字是", 1)[1]

        if not name:
            return None

        name = (
            name.replace("。", "")
            .replace(".", "")
            .replace("，", "")
            .replace(",", "")
            .replace("请你记住", "")
            .strip()
        )

        if not name:
            return None

        return MemoryReflectionResult(
            should_remember=True,
            memory_text=f"玩家告诉{npc.name}，自己的名字是{name}。",
            memory_type="profile",
            importance=4,
        )

    def _detect_action_memory(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        actions: list[AgentAction],
        executed_actions: list[ToolExecutionResult],
    ) -> MemoryReflectionResult | None:
        successful_tools = [
            result.tool
            for result in executed_actions
            if result.success
        ]

        if not successful_tools:
            return None

        memory_parts: list[str] = []

        for action in actions:
            if action.tool not in successful_tools:
                continue

            if action.tool == "create_quest":
                quest_id = action.args.get("quest_id")
                memory_parts.append(
                    f"玩家接受了来自{npc.name}的任务：{quest_id}。"
                )

            elif action.tool == "complete_quest":
                quest_id = action.args.get("quest_id")
                memory_parts.append(
                    f"玩家完成了与{npc.name}相关的任务：{quest_id}。"
                )

            elif action.tool == "add_item":
                item_id = action.args.get("item_id")
                memory_parts.append(
                    f"玩家从{npc.name}相关事件中获得了物品：{item_id}。"
                )

            elif action.tool == "remove_item":
                item_id = action.args.get("item_id")
                memory_parts.append(
                    f"玩家交付或失去了与{npc.name}相关的物品：{item_id}。"
                )

            elif action.tool == "update_relationship":
                delta = action.args.get("delta", 0)
                if delta > 0:
                    memory_parts.append(
                        f"玩家的行为提升了{npc.name}对玩家的信任，关系值增加了{delta}。"
                    )
                elif delta < 0:
                    memory_parts.append(
                        f"玩家的行为降低了{npc.name}对玩家的信任，关系值减少了{abs(delta)}。"
                    )

            elif action.tool == "set_world_flag":
                flag = action.args.get("flag")
                value = action.args.get("value")
                memory_parts.append(
                    f"玩家参与的事件改变了世界状态：{flag}={value}。"
                )

        if not memory_parts:
            return None

        importance = 3
        memory_type = self._select_memory_type(successful_tools)

        if "complete_quest" in successful_tools:
            importance = 5
        elif "create_quest" in successful_tools:
            importance = 4
        elif "update_relationship" in successful_tools:
            importance = 3

        return MemoryReflectionResult(
            should_remember=True,
            memory_text="".join(memory_parts),
            memory_type=memory_type,
            importance=importance,
        )

    def _select_memory_type(self, successful_tools: list[str]) -> str:
        if "complete_quest" in successful_tools or "create_quest" in successful_tools:
            return "quest"

        if "update_relationship" in successful_tools:
            return "relationship"

        if "set_world_flag" in successful_tools:
            return "world_event"

        if "add_item" in successful_tools or "remove_item" in successful_tools:
            return "item"

        return "general"
