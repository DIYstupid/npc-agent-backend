from math import ceil

from app.core.config import settings

try:
    import tiktoken
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None


class TokenBudgetService:
    """Small dependency-free token estimator used for prompt budgeting."""

    def __init__(self) -> None:
        self._encoding = self._load_encoding()

    def estimate_tokens(self, text: str | None) -> int:
        if not text:
            return 0

        if self._encoding is not None:
            return len(self._encoding.encode(text))

        cjk_chars = 0
        other_chars = 0

        for char in text:
            codepoint = ord(char)
            if (
                0x4E00 <= codepoint <= 0x9FFF
                or 0x3400 <= codepoint <= 0x4DBF
                or 0xF900 <= codepoint <= 0xFAFF
            ):
                cjk_chars += 1
            elif not char.isspace():
                other_chars += 1

        return cjk_chars + ceil(other_chars / 4)

    def trim_text_to_budget(self, text: str, token_budget: int) -> str:
        if token_budget <= 0 or not text:
            return ""

        if self._encoding is not None:
            tokens = self._encoding.encode(text)
            if len(tokens) <= token_budget:
                return text

            return self._encoding.decode(tokens[-token_budget:]).lstrip()

        estimated_tokens = self.estimate_tokens(text)
        if estimated_tokens <= token_budget:
            return text

        keep_ratio = token_budget / max(estimated_tokens, 1)
        keep_chars = max(0, int(len(text) * keep_ratio) - 12)
        if keep_chars <= 0:
            return ""

        return text[-keep_chars:].lstrip()

    def _load_encoding(self):
        if tiktoken is None:
            return None

        model_name = settings.LLM_MODEL

        try:
            return tiktoken.encoding_for_model(model_name)
        except Exception:
            try:
                return tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None
