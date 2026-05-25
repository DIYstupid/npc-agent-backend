import unittest

from app.services.token_budget_service import TokenBudgetService


class TokenBudgetServiceTests(unittest.TestCase):
    def test_estimate_and_trim_text(self) -> None:
        service = TokenBudgetService()
        text = "玩家帮助铁匠修复了旧剑 and carried an ancient sword."

        estimated = service.estimate_tokens(text)
        trimmed = service.trim_text_to_budget(text, 8)

        self.assertGreater(estimated, 0)
        self.assertTrue(trimmed)
        self.assertLessEqual(service.estimate_tokens(trimmed), 8)


if __name__ == "__main__":
    unittest.main()
