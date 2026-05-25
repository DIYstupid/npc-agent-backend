import json

import redis

from app.schemas.chat import ChatMessage
from app.services.conversation_summary_service import ConversationSummaryService


class RedisMemoryService:
    """
    Redis 版短期记忆服务。

    使用 Redis List 保存对话消息。

    Key:
      session:{player_id}:{npc_id}:messages

    Value:
      每条消息保存为 JSON 字符串：
      {
        "role": "player",
        "content": "我叫Gary"
      }
    """

    def __init__(
        self,
        host: str,
        port: int,
        db: int,
        max_messages: int = 10,
    ) -> None:
        self.max_messages = max_messages
        self.summary_service = ConversationSummaryService()

        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
        )

        # 启动时测试连接
        self.client.ping()

    def _build_key(self, player_id: str, npc_id: str) -> str:
        return f"session:{player_id}:{npc_id}:messages"

    def _build_summary_key(self, player_id: str, npc_id: str) -> str:
        return f"session:{player_id}:{npc_id}:summary"

    def get_messages(self, player_id: str, npc_id: str) -> list[ChatMessage]:
        key = self._build_key(player_id, npc_id)

        raw_messages = self.client.lrange(key, 0, -1)

        messages: list[ChatMessage] = []

        for raw_message in raw_messages:
            try:
                data = json.loads(raw_message)
                messages.append(
                    ChatMessage(
                        role=data["role"],
                        content=data["content"],
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return messages

    def get_summary(self, player_id: str, npc_id: str) -> str:
        key = self._build_summary_key(player_id, npc_id)
        return self.client.get(key) or ""

    def _decode_messages(self, raw_messages: list[str]) -> list[ChatMessage]:
        messages: list[ChatMessage] = []

        for raw_message in raw_messages:
            try:
                data = json.loads(raw_message)
                messages.append(
                    ChatMessage(
                        role=data["role"],
                        content=data["content"],
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return messages

    def add_message(
        self,
        player_id: str,
        npc_id: str,
        role: str,
        content: str,
    ) -> None:
        key = self._build_key(player_id, npc_id)

        message = ChatMessage(
            role=role,
            content=content,
        )

        self.client.rpush(
            key,
            json.dumps(
                message.model_dump(),
                ensure_ascii=False,
            ),
        )

        raw_messages = self.client.lrange(key, 0, -1)
        if len(raw_messages) > self.max_messages:
            overflow_raw_messages = raw_messages[:-self.max_messages]
            overflow_messages = self._decode_messages(overflow_raw_messages)
            summary_key = self._build_summary_key(player_id, npc_id)
            summary = self.summary_service.update_summary(
                existing_summary=self.client.get(summary_key) or "",
                overflow_messages=overflow_messages,
            )
            self.client.set(summary_key, summary)

        # 只保留最近 max_messages 条
        self.client.ltrim(key, -self.max_messages, -1)

    def clear_messages(self, player_id: str, npc_id: str) -> None:
        key = self._build_key(player_id, npc_id)
        summary_key = self._build_summary_key(player_id, npc_id)
        self.client.delete(key)
        self.client.delete(summary_key)

    def close(self) -> None:
        close_client = getattr(self.client, "close", None)
        if close_client is not None:
            close_client()

        self.client.connection_pool.disconnect()
