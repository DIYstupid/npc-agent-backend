import json
import unittest
import uuid
from pathlib import Path

from app.repositories.player_state_repository import PlayerStateRepository
from app.repositories.shared_knowledge_repository import SharedKnowledgeRepository
from app.schemas.chat import AgentAction
from app.schemas.tool import agent_action_json_schema
from app.services.game_service import GameService
from app.services.shared_knowledge_service import SharedKnowledgeService
from app.services.tool_service import ToolService


class ToolServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.db_path = tmp_root / f"player_state_{uuid.uuid4().hex}.db"
        self.knowledge_db_path = tmp_root / f"shared_knowledge_{uuid.uuid4().hex}.db"
        repository = PlayerStateRepository(db_path=str(self.db_path))
        self.game_service = GameService(repository)
        self.shared_knowledge_service = SharedKnowledgeService(
            repository=SharedKnowledgeRepository(db_path=str(self.knowledge_db_path))
        )
        self.tool_service = ToolService(
            self.game_service,
            shared_knowledge_service=self.shared_knowledge_service,
        )

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.db_path}{suffix}")
            if path.exists():
                path.unlink()
            knowledge_path = Path(f"{self.knowledge_db_path}{suffix}")
            if knowledge_path.exists():
                knowledge_path.unlink()

    def test_create_quest_is_idempotent(self) -> None:
        action = AgentAction(
            tool="create_quest",
            args={"quest_id": "unit_test_quest"},
        )

        first_result = self.tool_service.execute_action("player_001", action)
        second_result = self.tool_service.execute_action("player_001", action)
        player = self.game_service.get_player_state("player_001")

        self.assertTrue(first_result.success)
        self.assertEqual(first_result.data["status"], "created")
        self.assertTrue(second_result.success)
        self.assertEqual(second_result.data["status"], "already_active")
        self.assertEqual(player.active_quests.count("unit_test_quest"), 1)

    def test_add_item_is_idempotent(self) -> None:
        action = AgentAction(
            tool="add_item",
            args={"item_id": "unit_test_item"},
        )

        first_result = self.tool_service.execute_action("player_001", action)
        second_result = self.tool_service.execute_action("player_001", action)
        player = self.game_service.get_player_state("player_001")

        self.assertEqual(first_result.data["status"], "added")
        self.assertEqual(second_result.data["status"], "already_exists")
        self.assertEqual(player.inventory.count("unit_test_item"), 1)

    def test_move_player_updates_location(self) -> None:
        result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="move_player",
                args={"location": "north_road"},
            ),
        )
        player = self.game_service.get_player_state("player_001")

        self.assertTrue(result.success)
        self.assertEqual(result.data["status"], "moved")
        self.assertEqual(player.location, "north_road")

    def test_complete_quest_requires_objectives_when_defined(self) -> None:
        create_result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="create_quest",
                args={
                    "quest_id": "objective_quest",
                    "objectives": [
                        {
                            "objective_id": "talk_guard",
                            "type": "talk_to_npc",
                            "npc_id": "guard_001",
                        }
                    ],
                },
            ),
        )
        complete_result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="complete_quest",
                args={"quest_id": "objective_quest"},
            ),
        )

        self.assertTrue(create_result.success)
        self.assertFalse(complete_result.success)
        self.assertEqual(complete_result.data["status"], "objectives_incomplete")

    def test_invalid_tool_is_rejected(self) -> None:
        result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(tool="delete_player", args={}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.data["status"], "not_allowed")

    def test_agent_action_schema_lists_allowed_tool_contracts(self) -> None:
        schema_text = json.dumps(agent_action_json_schema(), sort_keys=True)

        for tool_name in self.tool_service.allowed_tools:
            self.assertIn(tool_name, schema_text)
        self.assertIn("quest_id", schema_text)
        self.assertIn("item_id", schema_text)
        self.assertIn("known_by_npc_ids", schema_text)

    def test_invalid_args_are_rejected_before_state_mutation(self) -> None:
        player_before = self.game_service.get_player_state("player_001")
        result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(tool="add_item", args={"item_id": ""}),
        )
        player_after = self.game_service.get_player_state("player_001")

        self.assertFalse(result.success)
        self.assertEqual(result.data["status"], "invalid_action")
        self.assertEqual(player_after.inventory, player_before.inventory)

    def test_wrong_arg_type_does_not_mutate_relationship(self) -> None:
        player_before = self.game_service.get_player_state("player_001")
        result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="update_relationship",
                args={"npc_id": "blacksmith_001", "delta": "many"},
            ),
        )
        player_after = self.game_service.get_player_state("player_001")

        self.assertFalse(result.success)
        self.assertEqual(result.data["status"], "invalid_action")
        self.assertEqual(player_after.relationships, player_before.relationships)

    def test_batch_exposes_raw_validated_and_executed_actions(self) -> None:
        batch = self.tool_service.execute_actions_with_validation(
            player_id="player_001",
            actions=[
                AgentAction(tool="add_item", args={"item_id": "schema_item"}),
                AgentAction(tool="remove_item", args={}),
                AgentAction(tool="delete_player", args={}),
            ],
        )

        self.assertEqual(len(batch.raw_actions), 3)
        self.assertEqual(
            [action.tool for action in batch.validated_actions],
            ["add_item"],
        )
        self.assertEqual(
            [result.data["status"] for result in batch.executed_actions],
            ["added", "invalid_action", "not_allowed"],
        )

    def test_publish_knowledge_creates_player_scoped_shared_event(self) -> None:
        result = self.tool_service.execute_action(
            player_id="player_001",
            action=AgentAction(
                tool="publish_knowledge",
                args={
                    "text": "The tavern keeper is looking for Gary.",
                    "source_npc_id": "tavernkeeper_001",
                    "subject_npc_ids": ["tavernkeeper_001"],
                    "known_by_npc_ids": ["blacksmith_001"],
                    "event_type": "request",
                },
            ),
        )

        events = self.shared_knowledge_service.get_relevant_events(
            player_id="player_001",
            npc_id="blacksmith_001",
            query="tavern",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["status"], "published")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].player_id, "player_001")
        self.assertEqual(events[0].subject_npc_ids, ["tavernkeeper_001"])


if __name__ == "__main__":
    unittest.main()
