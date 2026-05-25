import json
import uuid
from pathlib import Path
import unittest

from scripts.eval_agent_behavior import run_eval


class EvalAgentBehaviorTests(unittest.TestCase):
    def test_run_eval_writes_reports(self) -> None:
        tmp_root = Path("tests/.tmp")
        tmp_root.mkdir(parents=True, exist_ok=True)
        suffix = uuid.uuid4().hex
        cases_path = tmp_root / f"agent_cases_{suffix}.jsonl"
        json_report_path = tmp_root / f"eval_report_{suffix}.json"
        md_report_path = tmp_root / f"eval_report_{suffix}.md"

        cases_path.write_text(
            json.dumps(
                {
                    "case_id": "unit_eval_case",
                    "player_id": "player_001",
                    "npc_id": "blacksmith_001",
                    "message": "I will help you find silver ore.",
                    "expected_tools": ["create_quest", "update_relationship"],
                    "expected_knowledge_hit": False,
                    "expected_quest_state": {
                        "active": ["find_silver_ore"],
                        "completed": [],
                    },
                    "expected_reply_contains": ["silver ore"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        try:
            report = run_eval(
                cases_path=cases_path,
                json_report_path=json_report_path,
                md_report_path=md_report_path,
            )
            self.assertTrue(report["passed"])
            self.assertTrue(json_report_path.exists())
            self.assertTrue(md_report_path.exists())
            self.assertEqual(report["metrics"]["total_cases"], 1)
        finally:
            for path in (cases_path, json_report_path, md_report_path):
                if path.exists():
                    path.unlink()


if __name__ == "__main__":
    unittest.main()
