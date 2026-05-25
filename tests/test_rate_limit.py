import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import SimpleRateLimitMiddleware


def make_limited_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
        excluded_paths={"/health"},
    )

    @app.get("/limited")
    def limited() -> dict:
        return {"status": "ok"}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


class RateLimitTests(unittest.TestCase):
    def test_rate_limit_returns_uniform_error_body(self) -> None:
        client = TestClient(make_limited_app())

        self.assertEqual(client.get("/limited").status_code, 200)
        self.assertEqual(client.get("/limited").status_code, 200)
        response = client.get("/limited")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "rate_limit_exceeded")
        self.assertEqual(response.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", response.headers)

    def test_excluded_path_is_not_limited(self) -> None:
        client = TestClient(make_limited_app())

        for _ in range(5):
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
