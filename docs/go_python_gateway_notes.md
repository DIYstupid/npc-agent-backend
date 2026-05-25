# Go + Python Gateway Notes

## Why Split Go And Python?

Python is still the right runtime for the Agent layer because the project uses
FastAPI, LangGraph, Chroma, embedding models, prompt assembly, and LLM clients
there. Rewriting that logic in Go would add risk without improving the AI
behavior.

Go is added as the backend entry layer. It owns request-level engineering
concerns that are easy to describe and verify in interviews: HTTP/SSE gateway,
request IDs, timeout control, recovery, access logs, health checks, Redis
integration, and later DB/metrics/deployment work.

## Why Can't The LLM Modify State Directly?

LLM output is treated as an untrusted proposal. Real game state changes must go
through `ToolService` and `WorldActionService`, where tool names are
allowlisted, arguments are validated, repeated actions are idempotent, and state
machine rules decide whether an action is legal.

This keeps prompt generation separate from durable state mutation. It also makes
failures easier to debug because Trace records raw actions, validated actions,
and executed action results.

## How Does SSE Keep The Final State Consistent?

The stream uses the same `ChatPipeline` as synchronous chat. The runtime emits:

```text
start -> delta* -> final
```

`delta` events are only presentation data for progressive rendering. Durable
side effects are finalized by the pipeline before the `final` event is emitted.
If an error happens inside the stream, the runtime emits an `error` event instead
of silently closing the connection.

## How Are Python Runtime Failures Handled?

Go wraps calls to Python with a request context and timeout. If Python is slow or
unreachable, Go returns a clear JSON error envelope:

```json
{
  "error": {
    "code": "python_runtime_timeout",
    "message": "python runtime timed out",
    "request_id": "..."
  }
}
```

For SSE, the first version intentionally passes Python's SSE stream through
without token-level transformation. This preserves the existing Qt client
contract while moving the external entry point to Go.
