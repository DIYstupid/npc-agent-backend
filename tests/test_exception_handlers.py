import unittest

from fastapi.testclient import TestClient

from app.main import app


class ExceptionHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_business_exception_uses_uniform_error_body(self) -> None:
        response = self.client.get("/npcs/missing_npc")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "npc_not_found")
        self.assertEqual(payload["error"]["message"], "npc not found: missing_npc")
        self.assertEqual(
            payload["error"]["details"],
            {
                "resource": "npc",
                "identifier": "missing_npc",
            },
        )
        self.assertNotIn("detail", payload)

    def test_http_exception_uses_uniform_error_body(self) -> None:
        response = self.client.get("/missing-route")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "not_found")
        self.assertEqual(payload["error"]["message"], "Not Found")
        self.assertNotIn("detail", payload)

    def test_request_validation_uses_uniform_error_body(self) -> None:
        response = self.client.post(
            "/chat/blacksmith_001",
            json={
                "player_id": "player_001",
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "request_validation_error")
        self.assertEqual(payload["error"]["message"], "Request validation failed")
        self.assertTrue(payload["error"]["details"])
        self.assertNotIn("detail", payload)

    def test_chat_request_rejects_blank_message(self) -> None:
        response = self.client.post(
            "/chat/blacksmith_001",
            json={
                "player_id": "player_001",
                "message": "   ",
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "request_validation_error")

    def test_query_validation_rejects_out_of_range_limit(self) -> None:
        response = self.client.get(
            "/memory/long-term/search",
            params={
                "npc_id": "blacksmith_001",
                "player_id": "player_001",
                "query": "ore",
                "top_k": 100,
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "request_validation_error")

    def test_path_validation_rejects_invalid_resource_id(self) -> None:
        response = self.client.get("/npcs/bad id")

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "request_validation_error")


if __name__ == "__main__":
    unittest.main()
