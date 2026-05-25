from dataclasses import dataclass

from app.agent.prompts import build_npc_chat_prompt
from app.core.config import settings
from app.schemas.chat import ChatMessage
from app.schemas.context import ContextReport
from app.schemas.game import PlayerState
from app.schemas.memory import LongTermMemory
from app.schemas.npc import NPCProfile
from app.schemas.shared_knowledge import KnowledgeEvent
from app.services.token_budget_service import TokenBudgetService


@dataclass
class BuiltPromptContext:
    prompt: str
    report: ContextReport
    selected_short_term_memory: list[ChatMessage]
    selected_long_term_memory: list[LongTermMemory]
    selected_shared_knowledge: list[KnowledgeEvent]
    summary_memory: str


class ContextBuilderService:
    """Builds the final LLM prompt under explicit token budgets."""

    def __init__(self, token_budget_service: TokenBudgetService) -> None:
        self.token_budget_service = token_budget_service

    def build(
        self,
        request_id: str,
        npc: NPCProfile,
        player_state: PlayerState,
        player_message: str,
        short_term_memory: list[ChatMessage],
        summary_memory: str,
        long_term_memory: list[LongTermMemory],
        shared_knowledge: list[KnowledgeEvent] | None = None,
    ) -> BuiltPromptContext:
        shared_knowledge = shared_knowledge or []
        selected_short = self._select_latest_messages(
            messages=short_term_memory,
            token_budget=settings.SHORT_TERM_MEMORY_TOKEN_BUDGET,
        )
        selected_long = self._select_long_term_memories(
            memories=long_term_memory,
            token_budget=settings.LONG_TERM_MEMORY_TOKEN_BUDGET,
        )
        selected_knowledge = self._select_shared_knowledge(
            events=shared_knowledge,
            token_budget=settings.LONG_TERM_MEMORY_TOKEN_BUDGET,
        )
        selected_summary = self.token_budget_service.trim_text_to_budget(
            text=summary_memory,
            token_budget=settings.SUMMARY_MEMORY_TOKEN_BUDGET,
        )

        prompt = self._build_prompt(
            npc=npc,
            player_state=player_state,
            player_message=player_message,
            short_term_memory=selected_short,
            summary_memory=selected_summary,
            long_term_memory=selected_long,
            shared_knowledge=selected_knowledge,
        )

        selected_short, selected_summary, selected_long, selected_knowledge, prompt = self._fit_total_budget(
            npc=npc,
            player_state=player_state,
            player_message=player_message,
            selected_short=selected_short,
            selected_summary=selected_summary,
            selected_long=selected_long,
            selected_knowledge=selected_knowledge,
            prompt=prompt,
        )

        raw_prompt = self._build_prompt(
            npc=npc,
            player_state=player_state,
            player_message=player_message,
            short_term_memory=short_term_memory,
            summary_memory=summary_memory,
            long_term_memory=long_term_memory,
            shared_knowledge=shared_knowledge,
        )
        estimated_prompt_tokens = self.token_budget_service.estimate_tokens(prompt)
        raw_prompt_tokens = self.token_budget_service.estimate_tokens(raw_prompt)

        report = ContextReport(
            request_id=request_id,
            token_budget=settings.PROMPT_TOKEN_BUDGET,
            estimated_prompt_tokens=estimated_prompt_tokens,
            estimated_saved_tokens=max(0, raw_prompt_tokens - estimated_prompt_tokens),
            section_tokens={
                "player_message": self.token_budget_service.estimate_tokens(
                    player_message,
                ),
                "short_term_memory": self._estimate_messages(selected_short),
                "summary_memory": self.token_budget_service.estimate_tokens(
                    selected_summary,
                ),
                "long_term_memory": self._estimate_memories(selected_long),
                "shared_knowledge": self._estimate_shared_knowledge(selected_knowledge),
                "full_prompt": estimated_prompt_tokens,
            },
            selected_short_term_messages=len(selected_short),
            trimmed_short_term_messages=max(0, len(short_term_memory) - len(selected_short)),
            selected_long_term_memories=len(selected_long),
            trimmed_long_term_memories=max(0, len(long_term_memory) - len(selected_long)),
            selected_shared_knowledge_events=len(selected_knowledge),
            trimmed_shared_knowledge_events=max(
                0,
                len(shared_knowledge) - len(selected_knowledge),
            ),
            has_summary_memory=bool(selected_summary),
        )

        return BuiltPromptContext(
            prompt=prompt,
            report=report,
            selected_short_term_memory=selected_short,
            selected_long_term_memory=selected_long,
            selected_shared_knowledge=selected_knowledge,
            summary_memory=selected_summary,
        )

    def _select_latest_messages(
        self,
        messages: list[ChatMessage],
        token_budget: int,
    ) -> list[ChatMessage]:
        selected: list[ChatMessage] = []
        used_tokens = 0

        for message in reversed(messages):
            message_tokens = self.token_budget_service.estimate_tokens(
                f"{message.role}: {message.content}",
            )
            if selected and used_tokens + message_tokens > token_budget:
                break
            if not selected and message_tokens > token_budget:
                trimmed_content = self.token_budget_service.trim_text_to_budget(
                    message.content,
                    token_budget,
                )
                selected.append(
                    ChatMessage(
                        role=message.role,
                        content=trimmed_content,
                    )
                )
                break

            selected.append(message)
            used_tokens += message_tokens

        return list(reversed(selected))

    def _select_long_term_memories(
        self,
        memories: list[LongTermMemory],
        token_budget: int,
    ) -> list[LongTermMemory]:
        selected: list[LongTermMemory] = []
        used_tokens = 0

        ranked_memories = sorted(
            memories,
            key=lambda memory: memory.importance,
            reverse=True,
        )

        for memory in ranked_memories:
            memory_tokens = self.token_budget_service.estimate_tokens(memory.text)
            if selected and used_tokens + memory_tokens > token_budget:
                continue
            if not selected and memory_tokens > token_budget:
                trimmed_text = self.token_budget_service.trim_text_to_budget(
                    memory.text,
                    token_budget,
                )
                selected.append(
                    memory.copy(update={"text": trimmed_text})
                )
                break

            selected.append(memory)
            used_tokens += memory_tokens

        return selected

    def _select_shared_knowledge(
        self,
        events: list[KnowledgeEvent],
        token_budget: int,
    ) -> list[KnowledgeEvent]:
        selected: list[KnowledgeEvent] = []
        used_tokens = 0

        ranked_events = sorted(
            events,
            key=lambda event: (event.confidence, event.created_at or ""),
            reverse=True,
        )

        for event in ranked_events:
            event_tokens = self.token_budget_service.estimate_tokens(event.text)
            if selected and used_tokens + event_tokens > token_budget:
                continue
            if not selected and event_tokens > token_budget:
                trimmed_text = self.token_budget_service.trim_text_to_budget(
                    event.text,
                    token_budget,
                )
                selected.append(event.model_copy(update={"text": trimmed_text}))
                break

            selected.append(event)
            used_tokens += event_tokens

        return selected

    def _fit_total_budget(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        player_message: str,
        selected_short: list[ChatMessage],
        selected_summary: str,
        selected_long: list[LongTermMemory],
        selected_knowledge: list[KnowledgeEvent],
        prompt: str,
    ) -> tuple[list[ChatMessage], str, list[LongTermMemory], list[KnowledgeEvent], str]:
        while (
            self.token_budget_service.estimate_tokens(prompt)
            > settings.PROMPT_TOKEN_BUDGET
            and (selected_long or selected_knowledge)
        ):
            if selected_long:
                selected_long.pop()
            else:
                selected_knowledge.pop()
            prompt = self._build_prompt(
                npc,
                player_state,
                player_message,
                selected_short,
                selected_summary,
                selected_long,
                selected_knowledge,
            )

        while (
            self.token_budget_service.estimate_tokens(prompt)
            > settings.PROMPT_TOKEN_BUDGET
            and selected_short
        ):
            selected_short.pop(0)
            prompt = self._build_prompt(
                npc,
                player_state,
                player_message,
                selected_short,
                selected_summary,
                selected_long,
                selected_knowledge,
            )

        if (
            self.token_budget_service.estimate_tokens(prompt)
            > settings.PROMPT_TOKEN_BUDGET
            and selected_summary
        ):
            selected_summary = self.token_budget_service.trim_text_to_budget(
                selected_summary,
                max(0, settings.SUMMARY_MEMORY_TOKEN_BUDGET // 2),
            )
            prompt = self._build_prompt(
                npc,
                player_state,
                player_message,
                selected_short,
                selected_summary,
                selected_long,
                selected_knowledge,
            )

        return selected_short, selected_summary, selected_long, selected_knowledge, prompt

    def _build_prompt(
        self,
        npc: NPCProfile,
        player_state: PlayerState,
        player_message: str,
        short_term_memory: list[ChatMessage],
        summary_memory: str,
        long_term_memory: list[LongTermMemory],
        shared_knowledge: list[KnowledgeEvent],
    ) -> str:
        return build_npc_chat_prompt(
            npc=npc,
            player_state=player_state,
            player_message=player_message,
            short_term_memory=short_term_memory,
            summary_memory=summary_memory,
            long_term_memory=long_term_memory,
            shared_knowledge=shared_knowledge,
        )

    def _estimate_messages(self, messages: list[ChatMessage]) -> int:
        return sum(
            self.token_budget_service.estimate_tokens(
                f"{message.role}: {message.content}",
            )
            for message in messages
        )

    def _estimate_memories(self, memories: list[LongTermMemory]) -> int:
        return sum(
            self.token_budget_service.estimate_tokens(memory.text)
            for memory in memories
        )

    def _estimate_shared_knowledge(self, events: list[KnowledgeEvent]) -> int:
        return sum(
            self.token_budget_service.estimate_tokens(event.text)
            for event in events
        )
