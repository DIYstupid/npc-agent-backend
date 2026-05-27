import unittest

from scripts.load_test_api import RequestResult
from scripts.load_test_api import count_sse_events
from scripts.load_test_api import percentile
from scripts.load_test_api import summarize_results


class LoadTestApiTests(unittest.TestCase):
    def test_percentile_uses_nearest_rank(self) -> None:
        self.assertEqual(percentile([10, 20, 30, 40], 50), 20)
        self.assertEqual(percentile([10, 20, 30, 40], 95), 40)

    def test_count_sse_events(self) -> None:
        payload = (
            'event: start\ndata: {"request_id":"x"}\n\n'
            'event: delta\ndata: {"text":"h"}\n\n'
            'event: final\ndata: {"reply":"h"}\n\n'
        )
        self.assertEqual(count_sse_events(payload), 3)

    def test_summarize_results(self) -> None:
        summary = summarize_results(
            [
                RequestResult(ok=True, latency_ms=10, status_code=200, events=3),
                RequestResult(ok=True, latency_ms=30, status_code=200, events=3),
                RequestResult(ok=False, latency_ms=50, status_code=500, error="boom"),
            ],
            elapsed_seconds=1.5,
            stream=True,
            concurrency=2,
        )

        self.assertEqual(summary["total_requests"], 3)
        self.assertEqual(summary["successful_requests"], 2)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertAlmostEqual(summary["error_rate"], 1 / 3)
        self.assertEqual(summary["p95_latency_ms"], 30)
        self.assertEqual(summary["configured_concurrency"], 2)
        self.assertEqual(summary["sse_concurrent_connections"], 2)
        self.assertEqual(summary["sse_total_connections"], 3)
        self.assertEqual(summary["sse_events"], 6)
        self.assertEqual(summary["status_codes"], {"200": 2, "500": 1})


if __name__ == "__main__":
    unittest.main()
