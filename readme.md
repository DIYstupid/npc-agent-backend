# NPC Agent Backend

基于 LLM Agent 的游戏 NPC 行为决策、记忆和工具执行后端。

## 当前能力

- FastAPI NPC 聊天接口（同步 + SSE 流式，二者共用 `ChatPipeline` 三阶段域逻辑）
- SSE 聊天流式响应，支持客户端逐字渲染
- 玩家状态与任务持久化（SQLite）
- 短期记忆（Redis / 内存 fallback）、摘要记忆、长期向量记忆（Chroma）
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

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

如果只想离线调试，把 `LLM_PROVIDER=mock` 写进 `.env`。

## 测试

后端测试：

```powershell
python -m unittest discover -s tests -v
python scripts/eval_memory_behavior.py
```

SSE 聊天流测试覆盖：

- `ChatService.stream_chat()` 的 `start -> delta* -> final` 事件顺序。
- `delta.text` 拼接结果与 `final.reply` 一致。
- 流式完成后仍写入短期记忆和 Prompt Trace。
- `/chat/{npc_id}/stream` 返回 `text/event-stream`。

Qt 客户端测试命令见 [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)。

## 文档

- [docs/current_project_record.md](docs/current_project_record.md)：最新项目状态记录（推荐入口）
- [docs/project_handoff_overview.md](docs/project_handoff_overview.md)：项目接手总览
- [docs/interview_qa_full.md](docs/interview_qa_full.md)：完整版面试问答与八股要点
- [docs/interview_qa_phase1.md](docs/interview_qa_phase1.md)：阶段 1 面试问答
- [docs/phase1_backend_extensions.md](docs/phase1_backend_extensions.md)
- [docs/phase3_langgraph_and_qt_ui_plan.md](docs/phase3_langgraph_and_qt_ui_plan.md)
- [docs/backend_lifecycle.md](docs/backend_lifecycle.md)
- [AI_NPC_Agent_简历总结与优化计划.md](AI_NPC_Agent_简历总结与优化计划.md)
- [AI_NPC_Agent_阶段3_简历项目_STAR与学习要点.md](AI_NPC_Agent_阶段3_简历项目_STAR与学习要点.md)
- [clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)
