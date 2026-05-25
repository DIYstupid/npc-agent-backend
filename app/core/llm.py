import json

from openai import OpenAI

from app.core.config import settings
from app.schemas.chat import AgentAction
from app.schemas.llm import LLMChatResult
from app.schemas.tool import agent_action_json_schema

class BaseLLMClient:
    """
    LLM 客户端基类。
    """

    def generate(self, prompt: str) -> LLMChatResult:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM 客户端。

    用于无 API Key 时本地开发。
    """

    def generate(self, prompt: str) -> LLMChatResult:
        if "我愿意帮你找银矿石" in prompt or "帮你找银矿石" in prompt:
            return LLMChatResult(
                reply="如果你能带回一块银矿石，我就帮你修好这把剑。北边的废弃矿洞也许还有些矿脉。",
                actions=[
                    AgentAction(
                        tool="create_quest",
                        args={"quest_id": "find_silver_ore"},
                    ),
                    AgentAction(
                        tool="update_relationship",
                        args={
                            "npc_id": "blacksmith_001",
                            "delta": 5,
                        },
                    ),
                ],
            )

        if "我带来了银矿石" in prompt or ("silver_ore" in prompt and "背包" in prompt):
            return LLMChatResult(
                reply="不错，你真的把银矿石带回来了。把旧剑交给我，我会替你修好。",
                actions=[
                    AgentAction(
                        tool="remove_item",
                        args={"item_id": "silver_ore"},
                    ),
                    AgentAction(
                        tool="add_item",
                        args={"item_id": "repaired_sword"},
                    ),
                    AgentAction(
                        tool="complete_quest",
                        args={"quest_id": "find_silver_ore"},
                    ),
                    AgentAction(
                        tool="update_relationship",
                        args={
                            "npc_id": "blacksmith_001",
                            "delta": 10,
                        },
                    ),
                ],
            )

        if "我愿意调查狼群" in prompt or "调查狼群" in prompt:
            return LLMChatResult(
                reply="很好。去村外看看那些狼群的踪迹，回来向我汇报。",
                actions=[
                    AgentAction(
                        tool="create_quest",
                        args={"quest_id": "investigate_wolf_tracks"},
                    ),
                    AgentAction(
                        tool="update_relationship",
                        args={
                            "npc_id": "guard_001",
                            "delta": 5,
                        },
                    ),
                ],
            )

        if "你还记得我" in prompt or "记得我做过什么" in prompt or "我以前帮过你什么" in prompt:
            return LLMChatResult(
                reply=self._reply_long_term_memory(prompt),
                actions=[],
            )

        if "我叫什么" in prompt or "我的名字" in prompt:
            return LLMChatResult(
                reply=self._reply_player_name(prompt),
                actions=[],
            )

        if "blacksmith_001" in prompt:
            return LLMChatResult(
                reply=self._blacksmith_reply(prompt),
                actions=[],
            )

        if "healer_001" in prompt:
            return LLMChatResult(
                reply=self._healer_reply(prompt),
                actions=[],
            )

        if "guard_001" in prompt:
            return LLMChatResult(
                reply=self._guard_reply(prompt),
                actions=[],
            )

        return LLMChatResult(
            reply="我暂时还不知道该如何回应你。",
            actions=[],
        )

    def _reply_long_term_memory(self, prompt: str) -> str:
        if "找回了失踪的学徒" in prompt or "失踪学徒" in prompt:
            return "我当然记得。你曾帮我找回失踪的学徒，这份恩情我不会忘。"

        if "击退狼群" in prompt or "狼群" in prompt:
            return "我记得你曾帮村庄击退狼群。北境的人不会忘记真正出手相助的人。"

        if "银矿石" in prompt or "修复旧剑" in prompt:
            return "我记得你曾为了修复旧剑去寻找银矿石。那不是每个人都敢做的事。"

        return "我记得你曾与我有过交集，但具体细节一时有些模糊。"

    def _reply_player_name(self, prompt: str) -> str:
        if "我叫Gary" in prompt or "名字是Gary" in prompt:
            return "你叫Gary，我记得。守信的人，我一向不会忘。"

        return "你还没有正式告诉过我你的名字。"

    def _blacksmith_reply(self, prompt: str) -> str:
        if "tavernkeeper_001" in prompt or "tavern keeper" in prompt:
            return "The tavern keeper is looking for you. If I were you, I would not keep them waiting."

        if "我叫Gary" in prompt or "名字是Gary" in prompt:
            return "Gary，我记住了。若你守得住承诺，铁匠铺的大门会一直向你敞开。"

        if "修" in prompt or "剑" in prompt or "old_sword" in prompt:
            return "这把剑损坏得很严重。要修好它，我需要一块银矿石。"

        if "银矿" in prompt or "silver_ore" in prompt:
            return "银矿石在北边的废弃矿洞里还能找到一些，但那里最近不太安全。"

        return "有什么要修的东西就拿出来吧，但别浪费我的时间。"

    def _healer_reply(self, prompt: str) -> str:
        if "tavernkeeper_001" in prompt or "tavern keeper" in prompt:
            return "I heard the tavern keeper is looking for you. You should go when you can."

        if "我叫Gary" in prompt or "名字是Gary" in prompt:
            return "Gary，我记住了。若你受伤了，随时来找我。"

        if "狼毒" in prompt or "草药" in prompt or "治疗" in prompt:
            return "狼毒不能拖延。若你能找到月影草，我可以调配解毒药。"

        return "你看起来有些疲惫。北境最近不太平，外出时多加小心。"

    def _guard_reply(self, prompt: str) -> str:
        if "tavernkeeper_001" in prompt or "tavern keeper" in prompt:
            return "The tavern keeper has been asking after you. Make it quick, then report back if it concerns village safety."

        if "我叫Gary" in prompt or "名字是Gary" in prompt:
            return "Gary，我记住了。村庄现在需要可靠的人。"

        if "狼" in prompt or "袭击" in prompt:
            return "狼群最近越来越靠近村庄。我需要可靠的人去调查村外的踪迹。"

        return "村门附近禁止闲逛。如果你有重要情报，就直接告诉我。"

def get_llm_client() -> BaseLLMClient:
    """
    根据配置选择 LLM 客户端。
    """
    print("LLM_PROVIDER =", settings.LLM_PROVIDER)
    print("LLM_BASE_URL =", settings.LLM_BASE_URL)
    print("LLM_MODEL =", settings.LLM_MODEL)

    if settings.LLM_PROVIDER == "openai_compatible":
        print("Using OpenAICompatibleLLMClient")
        return OpenAICompatibleLLMClient()

    print("Using MockLLMClient")
    return MockLLMClient()



class OpenAICompatibleLLMClient(BaseLLMClient):
    """
    OpenAI-compatible LLM 客户端。

    支持：
    - OpenAI 官方 API
    - DeepSeek
    - Qwen / Moonshot / 硅基流动等 OpenAI-compatible API
    - 本地 vLLM / Ollama OpenAI-compatible endpoint

    只需要配置：
    - LLM_API_KEY
    - LLM_BASE_URL
    - LLM_MODEL
    """

    def __init__(self) -> None:
        if not settings.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY is required when LLM_PROVIDER=openai_compatible"
            )

        self.client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self.model = settings.LLM_MODEL

    def generate(self, prompt: str) -> LLMChatResult:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._system_instruction(),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={
                "type": "json_object",
            },
            stream=False,
        )

        raw_text = response.choices[0].message.content

        if raw_text is None:
            return LLMChatResult(
                reply="我一时没有想好该如何回应。",
                actions=[],
            )

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return LLMChatResult(
                reply=raw_text,
                actions=[],
            )

        return LLMChatResult(
            reply=data.get("reply", "我一时没有想好该如何回应。"),
            actions=[
                AgentAction(
                    tool=action.get("tool", ""),
                    args=action.get("args", {}),
                )
                for action in data.get("actions", [])
            ],
        )

    def close(self) -> None:
        self.client.close()

    def _system_instruction(self) -> str:
        action_schema = json.dumps(
            agent_action_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"""
You are a game NPC agent output adapter.

Return only a JSON object. Do not return Markdown or explanatory text.

The output format must be:
{{
  "reply": "What the NPC says to the player",
  "actions": [
    {{
      "tool": "tool_name",
      "args": {{}}
    }}
  ]
}}

Rules:
1. Keep the reply consistent with the NPC persona and visible context.
2. If the player is only chatting, return an empty actions array.
3. Use only tools allowed by the AgentAction schema below.
4. Do not invent player inventory, quest progress, or world state.
5. Do not duplicate a state change that already appears completed in context.
6. Every action must validate against this AgentAction JSON Schema:
{action_schema}
""".strip()
