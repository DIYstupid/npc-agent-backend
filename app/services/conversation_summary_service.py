from app.schemas.chat import ChatMessage


class ConversationSummaryService:
    """Maintains a compact extractive summary of messages that leave the window."""

    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max_chars

    def update_summary(
        self,
        existing_summary: str | None,
        overflow_messages: list[ChatMessage],
    ) -> str:
        if not overflow_messages:
            return existing_summary or ""

        lines = []
        for message in overflow_messages:
            role = "player" if message.role == "player" else "npc"
            lines.append(f"{role}: {message.content}")

        addition = " | ".join(lines)
        if existing_summary:
            summary = f"{existing_summary} | {addition}"
        else:
            summary = addition

        if len(summary) <= self.max_chars:
            return summary

        return summary[-self.max_chars:].lstrip(" |")
