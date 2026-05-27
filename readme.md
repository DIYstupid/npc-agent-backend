# NPC Agent Backend

## Local Docker Compose

Start the full local backend stack:

```powershell
docker compose up --build
```

Services:
- Go API Gateway: `http://127.0.0.1:8080`
- Python Agent Runtime: `http://127.0.0.1:8000`
- Redis: `127.0.0.1:16379`
- PostgreSQL: `127.0.0.1:15432`

Operational endpoints:
- `GET http://127.0.0.1:8080/health`
- `GET http://127.0.0.1:8080/metrics`
- `GET http://127.0.0.1:8080/debug/pprof/`

The compose stack uses `LLM_PROVIDER=mock` by default so it can boot without a
real LLM API key. Runtime SQLite, Chroma, and trace data is stored in Docker
volumes and not committed.

基于 LLM Agent 的游戏 NPC 行为决策、记忆和工具执行后端。

## 当前能力

- Go API Service 网关入口：统一 `request_id`、超时控制、panic recovery、access log、健康检查和 Python Runtime 代理
- FastAPI NPC 聊天接口（同步 + SSE 流式，二者共用 `ChatPipeline` 三阶段域逻辑）
- SSE 聊天流式响应，支持客户端逐字渲染
- 玩家状态与任务持久化（SQLite）
- 短期记忆（Redis / 内存 fallback）、摘要记忆、长期向量记忆（Chroma）
- RAG 文档知识库：Markdown/TXT 导入、chunk、Chroma 检索、关键词过滤、prompt 注入和来源引用
- `ReflectionWorker` 异步沉淀长期记忆，不阻塞响应
- 多 NPC 共享情报与一致性（`KnowledgeEvent`，scope/known_by/subject 三段可见性）
- 长期记忆管理接口
- 工具白名单与幂等执行（9 个工具）
- 世界状态机：`WorldActionService` 是唯一可改世界状态的执行层
- LangGraph `QuestAgent` / `WorldAgent`，`AsyncSqliteSaver` checkpoint
- 自然语言世界行动入口（`POST /world/interactions`），解析后复用状态机校验
- 接口限流 `SimpleRateLimitMiddleware`（默认 120 req / 60s / per IP）
- Prompt Trace 持久化与 Debug API（含共享情报与 agent trace）
- 可选 `tiktoken` token 预算估算
- LLM：`MockLLMClient` 离线 或 `OpenAICompatibleLLMClient`（任意 OpenAI 兼容 API，含 DeepSeek 等）
- `unittest` 43 个测试 + 行为评估脚本 + Qt 客户端 4 个 C++ 测试

## 架构

```text
Qt Debug Console / Future Client
        |
        v
Go API Service
  - HTTP / SSE 统一入口
  - request_id / timeout / recover / access log
  - Python Runtime 和 Redis 健康检查
        |
        v
Python Agent Runtime
  - FastAPI API
  - ChatPipeline / LangGraph QuestAgent / WorldAgent
  - Chroma 长期记忆、Prompt Trace、ToolService、WorldActionService
```

当前拆分原则是：Go 负责后端工程化入口和跨服务控制，Python 保留 Agent、Prompt、RAG/Memory、LLM 和状态机业务逻辑。

## 主要接口

Go API Service 当前对外暴露：

- `GET /health`
- `POST /chat/{npc_id}`
- `POST /chat/{npc_id}/stream`

Python Agent Runtime 暴露完整业务接口：

- `GET /health`
- `GET /npcs`
- `GET /game/state/{player_id}`
- `POST /chat/{npc_id}`
- `POST /chat/{npc_id}/stream`
- `GET /chat/history/{player_id}/{npc_id}`
- `DELETE /chat/history/{player_id}/{npc_id}`
- `POST /chat/{npc_id}/debug-prompt`
- `GET /memory/summary/{player_id}/{npc_id}`
- `POST /memory/long-term`
- `GET /memory/long-term`
- `GET /memory/long-term/search`
- `PATCH /memory/long-term/{memory_id}`
- `DELETE /memory/long-term/{memory_id}`
- `POST /rag/documents`
- `GET /rag/search`
- `POST /knowledge/events`
- `GET /knowledge/events`
- `GET /knowledge/events/{event_id}`
- `PATCH /knowledge/events/{event_id}`
- `POST /knowledge/events/{event_id}/known-by/{npc_id}`
- `POST /knowledge/events/{event_id}/resolve`
- `POST /quest/run`
- `POST /quest/{player_id}/{quest_id}/create`
- `POST /quest/{player_id}/{quest_id}/advance`
- `POST /quest/{player_id}/{quest_id}/complete`
- `GET /quest/{player_id}`
- `POST /world/events`
- `GET /world/events`
- `GET /debug/traces`
- `GET /debug/traces/latest`
- `GET /debug/traces/{request_id}`

## Redis

如果需要短期记忆使用 Redis，建议用 Docker Compose 按项目名启动：

```powershell
docker compose -p npc-agent-backend -f docker-compose.redis.yml up -d redis
```

这会生成带项目名前缀的容器和网络，便于和其他本地项目隔离。

## 本地运行 Python Runtime

完整 RAG / 长期记忆本地 embedding 能力需要额外安装 `requirements-ml.txt`。
该文件固定使用 CPU-only PyTorch，避免 Linux Docker 构建拉入 CUDA 运行时依赖。
如果只安装基础依赖，服务仍会启动，RAG 和长期记忆会使用 hash embedding fallback。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ml.txt
uvicorn app.main:app --reload
```

如果只想离线调试，把 `LLM_PROVIDER=mock` 写进 `.env`。

## 本地运行 Go API Service

先启动 Python Runtime 和 Redis，然后启动 Go 网关：

```powershell
cd services/go-api
go mod tidy
go run ./cmd/api
```

默认配置：

- Go API：`http://127.0.0.1:8080`
- Python Runtime：`http://127.0.0.1:8000`
- Redis：`127.0.0.1:6379`

Go 健康检查：

```powershell
curl http://127.0.0.1:8080/health
```

通过 Go 代理同步聊天：

```powershell
curl -X POST http://127.0.0.1:8080/chat/blacksmith_001 `
  -H "Content-Type: application/json" `
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

通过 Go 代理 SSE 流式聊天：

```powershell
curl -N -X POST http://127.0.0.1:8080/chat/blacksmith_001/stream `
  -H "Content-Type: application/json" `
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

常用环境变量：

- `GO_API_ADDR`
- `PYTHON_RUNTIME_BASE_URL`
- `REQUEST_TIMEOUT_MS`
- `REDIS_ADDR`

## Demo 场景

推荐演示路径：

1. 启动 Redis、Python Runtime 和 Go API Service。
2. 打开 Qt Debug Console 或直接调用 Go `POST /chat/{npc_id}/stream`。
3. 发送关于狼群、任务或 NPC 情报的问题，观察 SSE `start -> delta* -> final`。
4. 查看 `GET /debug/traces/latest`，确认 prompt context、actions、executed_actions 和 token budget。
5. 调用 `POST /rag/documents` 导入一段 Markdown/TXT 知识，再用聊天问题触发 RAG chunk 进入 prompt。
6. 调用 `GET /debug/traces/latest`，确认 `selected_rag_chunks` 和回答 `citations`。
7. 调用 `GET /game/state/{player_id}` 或知识库接口，验证工具执行和共享情报写入结果。

## 测试

后端测试：

```powershell
python -m unittest discover -s tests -v
python scripts/eval_memory_behavior.py
```

Go 网关测试：

```powershell
cd services/go-api
go test ./...
```

Go API load test after Docker Compose is healthy:

```powershell
python scripts/load_test_go_api.py --mode both --requests 40 --concurrency 8 --timeout-seconds 30
```

The script covers `POST /chat/{npc_id}` and `POST /chat/{npc_id}/stream`,
then writes QPS, P95 latency, error rate, and SSE concurrency results to
`eval/load_test_report.json` and `eval/load_test_report.md`.

SSE 聊天流测试覆盖：

- `ChatService.stream_chat()` 的 `start -> delta* -> final` 事件顺序。
- `delta.text` 拼接结果与 `final.reply` 一致。
- 流式完成后仍写入短期记忆和 Prompt Trace。
- `/chat/{npc_id}/stream` 返回 `text/event-stream`。

Qt 客户端测试命令见 [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)。

## 文档

- [docs/current_project_record.md](docs/current_project_record.md)：最新项目状态记录（推荐入口）
- [docs/ai_backend_improvement_plan.md](docs/ai_backend_improvement_plan.md)：AI 应用与后端工程化改造计划
- [docs/api_contract.md](docs/api_contract.md)：Python Agent Runtime API/SSE 契约
- [docs/go_python_gateway_notes.md](docs/go_python_gateway_notes.md)：Go + Python 服务拆分面试讲解
- [docs/project_handoff_overview.md](docs/project_handoff_overview.md)：项目接手总览
- [docs/interview_qa_full.md](docs/interview_qa_full.md)：完整版面试问答与八股要点
- [docs/interview_qa_phase1.md](docs/interview_qa_phase1.md)：阶段 1 面试问答
- [docs/phase1_backend_extensions.md](docs/phase1_backend_extensions.md)
- [docs/phase3_langgraph_and_qt_ui_plan.md](docs/phase3_langgraph_and_qt_ui_plan.md)
- [docs/backend_lifecycle.md](docs/backend_lifecycle.md)
- [AI_NPC_Agent_简历总结与优化计划.md](AI_NPC_Agent_简历总结与优化计划.md)
- [AI_NPC_Agent_阶段3_简历项目_STAR与学习要点.md](AI_NPC_Agent_阶段3_简历项目_STAR与学习要点.md)
- [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)
