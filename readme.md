# NPC Agent Backend

## 项目简介 / Project Overview

这是一个面向游戏 NPC 的 AI Agent 应用项目，主线是 **Python FastAPI
Agent 后端 + C++/Qt Debug Console**。项目覆盖 LLM 对话、短期记忆、长期
向量记忆、RAG 知识检索、工具调用、世界状态更新、Prompt Trace、SSE 流式
响应和 Qt 调试面板。

当前架构更适合应届生 AI 应用岗位和 C++/Qt 客户端岗位的简历叙事：

- **AI 应用方向**：突出 Agent pipeline、RAG、记忆系统、工具调用、评测、
  FastAPI 接口和可观测性。
- **客户端方向**：突出 C++/Qt 桌面调试面板、异步网络请求、SSE 解析、JSON
  渲染、错误/超时处理和复杂状态展示。

NPC Agent Backend is a game-NPC AI Agent application built around a **Python
FastAPI runtime and a C++/Qt debug console**. It includes LLM dialogue,
short-term memory, long-term vector memory, RAG retrieval, tool execution,
world-state updates, prompt tracing, SSE streaming, and a desktop debugging UI.

The project keeps the story focused on AI application engineering and C++/Qt
client engineering.

## 工程化结果 / Engineering Proof Points

- Python 测试：`54 tests OK`。
- 压测脚本：覆盖 `POST /chat/{npc_id}` 和 `POST /chat/{npc_id}/stream`。
- 最近本地压测：`40` 个 chat 请求和 `40` 个 SSE 请求，并发 `8`；
  chat `44.75 QPS` / `P95 348 ms`，SSE `32.15 QPS` / `P95 284 ms`，
  错误率 `0.00%`。
- Qt Debug Console 默认连接 `http://127.0.0.1:8000`，可用于展示聊天、
  trace、memory、RAG context 和 actions。

## 架构 / Architecture

```text
C++/Qt Debug Console / API Client
        |
        v
Python FastAPI Agent Runtime
  - ChatPipeline / SSE streaming
  - LangGraph QuestAgent / WorldAgent
  - Redis or in-memory short-term memory
  - Chroma-backed long-term memory and RAG
  - ToolService / WorldActionService
  - Prompt Trace / Debug API
```

核心原则：

- Python 负责 Agent、Prompt、RAG、Memory、LLM、状态机和 API 编排。
- Qt 负责客户端调试体验，包括流式聊天、Trace、Memory、Context、Actions
  等可视化面板。
- Docker Compose 只启动 Python Runtime、Redis 和 PostgreSQL，降低部署和
  面试解释复杂度。

## 当前能力

- FastAPI NPC 聊天接口，同步 + SSE 流式共用 `ChatPipeline`。
- SSE 聊天流式响应，支持客户端逐字渲染。
- 玩家状态与任务持久化。
- 短期记忆，支持 Redis 和内存 fallback。
- 摘要记忆、长期向量记忆和长期记忆管理接口。
- RAG 文档知识库：Markdown/TXT 导入、chunk、Chroma 检索、关键词过滤、
  prompt 注入和来源引用。
- `ReflectionWorker` 异步沉淀长期记忆，不阻塞主响应。
- 多 NPC 共享情报与一致性建模。
- 工具白名单与幂等执行。
- 世界状态机：`WorldActionService` 作为唯一可修改世界状态的执行层。
- LangGraph `QuestAgent` / `WorldAgent` 和 checkpoint。
- 自然语言世界行动入口，解析后复用状态机校验。
- 应用内限流 `SimpleRateLimitMiddleware`。
- Prompt Trace 持久化与 Debug API。
- 可选 `tiktoken` token 预算估算。
- LLM 支持 `MockLLMClient` 离线调试和 `OpenAICompatibleLLMClient`。
- C++/Qt Debug Console：后端健康检查、NPC 列表、聊天、SSE、Trace、
  Memory、Context、Actions 等调试视图。

## Local Docker Compose

启动本地后端栈：

```powershell
docker compose up --build
```

服务：

- Python Agent Runtime: `http://127.0.0.1:8000`
- Redis: `127.0.0.1:16379`
- PostgreSQL: `127.0.0.1:15432`

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

Compose 默认使用 `LLM_PROVIDER=mock`，不需要真实 LLM API key 即可启动。运行时
SQLite、Chroma、trace 数据保存在 Docker volume 或本地数据目录中，不应提交。

## 本地运行 Python 后端

完整 RAG / 长期记忆本地 embedding 能力需要额外安装 `requirements-ml.txt`。
如果只安装基础依赖，服务仍会启动，RAG 和长期记忆会使用 hash embedding
fallback。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ml.txt
uvicorn app.main:app --reload
```

离线调试建议在 `.env` 中设置：

```env
LLM_PROVIDER=mock
```

## Redis

如果只需要单独启动 Redis：

```powershell
docker compose -p npc-agent-backend -f docker-compose.redis.yml up -d redis
```

## 主要接口

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

## Demo 场景

推荐演示路径：

1. 启动 Python 后端，或使用 `docker compose up --build`。
2. 打开 Qt Debug Console，API URL 使用 `http://127.0.0.1:8000`。
3. 选中 `blacksmith_001`，玩家 ID 使用 `player_001`。
4. 发送关于狼群、任务或 NPC 情报的问题，观察 SSE 流式回复。
5. 查看 Qt 里的 Context / Actions / Trace / Memory 面板。
6. 调用 `POST /rag/documents` 导入一段 Markdown/TXT 知识，再用聊天触发
   RAG chunk 进入 prompt。
7. 查看 `GET /debug/traces/latest` 或 Qt Trace 面板，确认
   `selected_rag_chunks`、actions 和 token budget。

## 截图建议 / Screenshot Checklist

当前只需要 Qt 界面截图即可。建议在本地启动后端和 Qt Debug Console 后截两张：

1. **Qt 主界面流式聊天截图**
   - API URL 填 `http://127.0.0.1:8000`。
   - 选中 `blacksmith_001`，玩家 ID 使用 `player_001`。
   - 发送一句和任务或传闻相关的问题，例如 `Any news about the wolves?`。
   - 截图里尽量包含：聊天区、API 地址、Context 或 Actions 面板、NPC 回复。

2. **Qt Trace/Memory 调试截图**
   - 在完成一次聊天后切到 Trace 或 Memory 面板。
   - 截图里尽量包含：trace 列表、选中的 trace 详情、context report、
     actions/executed actions，或者长期记忆列表。

## 测试与压测

后端测试：

```powershell
python -m unittest discover -s tests -v
python scripts/eval_memory_behavior.py
```

压测 Python FastAPI chat 和 SSE：

```powershell
python scripts/load_test_api.py --mode both --requests 40 --concurrency 8 --timeout-seconds 30
```

压测脚本会生成 QPS、P95 latency、错误率和 SSE 连接统计，并写入：

- `eval/load_test_report.json`
- `eval/load_test_report.md`

压测报告默认不提交，只提交脚本和 README。

SSE 聊天流测试覆盖：

- `ChatService.stream_chat()` 的 `start -> delta* -> final` 事件顺序。
- `delta.text` 拼接结果与 `final.reply` 一致。
- 流式完成后仍写入短期记忆和 Prompt Trace。
- `/chat/{npc_id}/stream` 返回 `text/event-stream`。

Qt 客户端测试命令见 [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)。

## 文档

- 启动后访问 `http://127.0.0.1:8000/docs` 查看 FastAPI Swagger 文档。
- [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)：Qt Debug Console 构建、运行和测试说明。
