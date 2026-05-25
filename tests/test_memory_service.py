import unittest

from app.services.memory_service import MemoryService


class MemoryServiceTests(unittest.TestCase):
    def test_overflow_messages_are_rolled_into_summary(self) -> None:
        memory_service = MemoryService(max_messages=2)

        for index in range(4):
            memory_service.add_message(
                player_id="player_001",
                npc_id="blacksmith_001",
                role="player",
                content=f"message {index}",
            )

        messages = memory_service.get_messages(
            player_id="player_001",
            npc_id="blacksmith_001",
        )
        summary = memory_service.get_summary(
            player_id="player_001",
            npc_id="blacksmith_001",
        )

        self.assertEqual(len(messages), 2)
        self.assertIn("message 0", summary)
        self.assertIn("message 1", summary)


if __name__ == "__main__":
    unittest.main()
