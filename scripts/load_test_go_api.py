import argparse
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_NPC_ID = "blacksmith_001"
DEFAULT_PLAYER_ID = "player_001"
DEFAULT_MESSAGE = "Any news about the wolves?"
DEFAULT_JSON_REPORT_PATH = Path("eval/load_test_report.json")
DEFAULT_MD_REPORT_PATH = Path("eval/load_test_report.md")


@dataclass(frozen=True)
class RequestResult:
    ok: bool
    latency_ms: int
    status_code: int | None
    error: str | None = None
    events: int = 0


def run_load_test(
    base_url: str = DEFAULT_BASE_URL,
    npc_id: str = DEFAULT_NPC_ID,
    player_id: str = DEFAULT_PLAYER_ID,
    message: str = DEFAULT_MESSAGE,
    mode: str = "both",
    requests: int = 20,
    concurrency: int = 4,
    timeout_seconds: float = 30.0,
    json_report_path: Path = DEFAULT_JSON_REPORT_PATH,
    md_report_path: Path = DEFAULT_MD_REPORT_PATH,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    report: dict[str, Any] = {
        "base_url": base_url,
        "npc_id": npc_id,
        "player_id": player_id,
        "message": message,
        "mode": mode,
        "requests_per_mode": requests,
        "concurrency": concurrency,
        "timeout_seconds": timeout_seconds,
        "results": {},
    }

    if mode in ("chat", "both"):
        report["results"]["chat"] = run_endpoint_benchmark(
            endpoint_url=f"{base_url}/chat/{npc_id}",
            player_id=player_id,
            message=message,
            requests=requests,
            concurrency=concurrency,
            timeout_seconds=timeout_seconds,
            stream=False,
        )

    if mode in ("sse", "both"):
        report["results"]["sse"] = run_endpoint_benchmark(
            endpoint_url=f"{base_url}/chat/{npc_id}/stream",
            player_id=player_id,
            message=message,
            requests=requests,
            concurrency=concurrency,
            timeout_seconds=timeout_seconds,
            stream=True,
        )

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_report_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def run_endpoint_benchmark(
    endpoint_url: str,
    player_id: str,
    message: str,
    requests: int,
    concurrency: int,
    timeout_seconds: float,
    stream: bool,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    results: list[RequestResult] = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                post_chat_request,
                endpoint_url,
                player_id,
                f"{message} #{index}",
                timeout_seconds,
                stream,
            )
            for index in range(requests)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    elapsed_seconds = time.perf_counter() - started_at
    return summarize_results(
        results,
        elapsed_seconds,
        stream=stream,
        concurrency=concurrency,
    )


def post_chat_request(
    endpoint_url: str,
    player_id: str,
    message: str,
    timeout_seconds: float,
    stream: bool,
) -> RequestResult:
    payload = json.dumps(
        {
            "player_id": player_id,
            "message": message,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        },
        method="POST",
    )

    started_at = time.perf_counter()
    status_code: int | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status
            body = response.read()
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        events = count_sse_events(body.decode("utf-8", errors="replace")) if stream else 0
        return RequestResult(
            ok=200 <= status_code < 300,
            latency_ms=elapsed_ms,
            status_code=status_code,
            events=events,
        )
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return RequestResult(
            ok=False,
            latency_ms=elapsed_ms,
            status_code=exc.code,
            error=str(exc),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return RequestResult(
            ok=False,
            latency_ms=elapsed_ms,
            status_code=status_code,
            error=str(exc),
        )


def summarize_results(
    results: list[RequestResult],
    elapsed_seconds: float,
    stream: bool = False,
    concurrency: int = 0,
) -> dict[str, Any]:
    total = len(results)
    successes = sum(1 for result in results if result.ok)
    failures = total - successes
    latencies = [result.latency_ms for result in results]
    successful_latencies = [result.latency_ms for result in results if result.ok]
    status_codes: dict[str, int] = {}

    for result in results:
        key = str(result.status_code) if result.status_code is not None else "none"
        status_codes[key] = status_codes.get(key, 0) + 1

    return {
        "total_requests": total,
        "successful_requests": successes,
        "failed_requests": failures,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "qps": round(total / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0,
        "success_qps": round(successes / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0,
        "error_rate": safe_ratio(failures, total),
        "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p50_latency_ms": percentile(successful_latencies or latencies, 50),
        "p95_latency_ms": percentile(successful_latencies or latencies, 95),
        "max_latency_ms": max(latencies) if latencies else 0,
        "status_codes": status_codes,
        "configured_concurrency": concurrency,
        "sse_concurrent_connections": concurrency if stream else 0,
        "sse_total_connections": total if stream else 0,
        "sse_events": sum(result.events for result in results),
        "sample_errors": [result.error for result in results if result.error][:5],
    }


def count_sse_events(payload: str) -> int:
    return sum(
        1
        for raw_event in payload.strip().split("\n\n")
        if raw_event.strip().startswith("event:")
    )


def percentile(values: list[int], percentile_value: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(
        0,
        min(
            len(ordered) - 1,
            round((percentile_value / 100) * len(ordered) + 0.5) - 1,
        ),
    )
    return ordered[index]


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Go API Load Test Report",
        "",
        f"- Base URL: `{report['base_url']}`",
        f"- Mode: `{report['mode']}`",
        f"- Requests per mode: {report['requests_per_mode']}",
        f"- Concurrency: {report['concurrency']}",
        "",
        "## Results",
        "",
    ]

    for name, result in report["results"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Total requests: {result['total_requests']}",
                f"- Successful requests: {result['successful_requests']}",
                f"- Failed requests: {result['failed_requests']}",
                f"- QPS: {result['qps']}",
                f"- Success QPS: {result['success_qps']}",
                f"- Error rate: {result['error_rate']:.2%}",
                f"- Avg latency ms: {result['avg_latency_ms']}",
                f"- P50 latency ms: {result['p50_latency_ms']}",
                f"- P95 latency ms: {result['p95_latency_ms']}",
                f"- Max latency ms: {result['max_latency_ms']}",
                f"- Configured concurrency: {result['configured_concurrency']}",
                f"- Status codes: `{result['status_codes']}`",
            ]
        )
        if result["sse_concurrent_connections"]:
            lines.extend(
                [
                    f"- SSE concurrent connections: {result['sse_concurrent_connections']}",
                    f"- SSE total connections: {result['sse_total_connections']}",
                    f"- SSE events: {result['sse_events']}",
                ]
            )
        if result["sample_errors"]:
            lines.append(f"- Sample errors: `{result['sample_errors']}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a lightweight load test against Go API chat endpoints.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--npc-id", default=DEFAULT_NPC_ID)
    parser.add_argument("--player-id", default=DEFAULT_PLAYER_ID)
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--mode", choices=("chat", "sse", "both"), default="both")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT_PATH)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_load_test(
        base_url=args.base_url,
        npc_id=args.npc_id,
        player_id=args.player_id,
        message=args.message,
        mode=args.mode,
        requests=args.requests,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
        json_report_path=args.json_report,
        md_report_path=args.md_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    failed = any(result["failed_requests"] > 0 for result in report["results"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
