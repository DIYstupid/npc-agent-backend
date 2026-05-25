# Go API Service

Go API Service is the HTTP/SSE gateway in front of the existing Python Agent
Runtime. It keeps AI behavior in Python and owns backend concerns such as
request IDs, timeouts, recovery, access logs, health checks, and proxying.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `GO_API_ADDR` | `:8080` | Go server listen address. |
| `PYTHON_RUNTIME_BASE_URL` | `http://127.0.0.1:8000` | FastAPI runtime base URL. |
| `REQUEST_TIMEOUT_MS` | `30000` | Request timeout for incoming and proxied calls. |
| `REDIS_ADDR` | `127.0.0.1:6379` | Redis address used by health checks. Empty disables Redis checks. |
| `DB_ADDR` | empty | TCP address for DB health checks, for example `127.0.0.1:5432`. Empty disables DB checks. |
| `METRICS_ENABLED` | `true` | Enables `GET /metrics` in Prometheus text format. |
| `PPROF_ENABLED` | `true` | Enables Go pprof under `/debug/pprof/`. |
| `RATE_LIMIT_ENABLED` | `true` | Enables Redis-backed fixed-window rate limiting for proxied routes. |
| `RATE_LIMIT_REQUESTS` | `120` | Requests allowed per client IP within the rate-limit window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed rate-limit window size. |
| `RATE_LIMIT_EXCLUDED_PATHS` | `/health,/metrics,/debug/pprof` | Comma-separated path prefixes excluded from rate limiting. |

## Run

```powershell
cd services/go-api
go mod tidy
go run ./cmd/api
```

Health check:

```powershell
curl http://127.0.0.1:8080/health
```

Metrics and pprof:

```powershell
curl http://127.0.0.1:8080/metrics
curl http://127.0.0.1:8080/debug/pprof/
```

Chat proxy:

```powershell
curl -X POST http://127.0.0.1:8080/chat/blacksmith_001 `
  -H "Content-Type: application/json" `
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

SSE proxy:

```powershell
curl -N -X POST http://127.0.0.1:8080/chat/blacksmith_001/stream `
  -H "Content-Type: application/json" `
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

## Test

```powershell
cd services/go-api
go test ./...
```
