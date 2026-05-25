from app.schemas.chat import ChatMessage
from app.services.conversation_summary_service import ConversationSummaryService


class MemoryService:
    """
    内存版短期记忆服务。

    用于：
    - 本地快速开发
    - Redis 不可用时 fallback
    """

    def __init__(self, max_messages: int = 10) -> None:
        self.max_messages = max_messages
        self._store: dict[str, list[ChatMessage]] = {}
        self._summary_store: dict[str, str] = {}
        self.summary_service = ConversationSummaryService()

    def _build_key(self, player_id: str, npc_id: str) -> str:
        return f"session:{player_id}:{npc_id}:messages"

    def _build_summary_key(self, player_id: str, npc_id: str) -> str:
        return f"session:{player_id}:{npc_id}:summary"

    def get_messages(self, player_id: str, npc_id: str) -> list[ChatMessage]:
        key = self._build_key(player_id, npc_id)
        return self._store.get(key, [])

    def get_summary(self, player_id: str, npc_id: str) -> str:
        key = self._build_summary_key(player_id, npc_id)
        return self._summary_store.get(key, "")

    def add_message(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
    ) -> None:
        key = self._build_key(player_id, npc_id)

        if key not in self._store:
            self._store[key] = []

        self._store[key].append(
            ChatMessage(
                role=role,
                content=content,
            )
        )

        if len(self._store[key]) > self.max_messages:
            overflow_messages = self._store[key][:-self.max_messages]
            summary_key = self._build_summary_key(player_id, npc_id)
            self._summary_store[summary_key] = self.summary_service.update_summary(
                existing_summary=self._summary_store.get(summary_key, ""),
                overflow_messages=overflow_messages,
            )
            self._store[key] = self._store[key][-self.max_messages:]

    def clear_messages(self, player_id: str, npc_id: str) -> None:
        key = self._build_key(player_id, npc_id)
        summary_key = self._build_summary_key(player_id, npc_id)
        self._store.pop(key, None)
        self._summary_store.pop(summary_key, None)

    def close(self) -> None:
        self._store.clear()
        self._summary_store.clear()
