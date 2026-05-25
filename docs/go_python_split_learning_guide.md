# Go + Python 拆分改造学习指南

更新时间：2026-05-23

## 0. 学习目标

本文配合 `docs/go_python_backend_split_plan.md` 使用。目标不是把 Go、LangGraph、Redis、DB 全部学到很深，而是让你在改造项目后能讲清楚：

- 为什么要把 FastAPI 单体拆成 Go API Service + Python Agent Runtime。
- 一次聊天请求从 Qt 客户端到 Go、Python、Redis、DB、Trace 的完整链路。
- 为什么 LLM 不能直接改状态，必须经过 ToolService 和状态机。
- Go 侧如何保证超时、限流、幂等、SSE 流式响应和状态一致性。
- Python 侧为什么继续保留 LangGraph、Chroma、embedding 和 Prompt 构建。

最终你需要能把项目讲成“工程化后端系统”，而不是单纯“AI demo”。

## 1. Go 后端基础

重点学习：

- `context.Context`：请求超时、取消、跨服务调用传递。
- goroutine / channel / mutex：并发基础，知道什么时候该用、什么时候不该用。
- `net/http` 请求处理模型。
- error handling。
- handler / service / repository / client 分层。

资料：

- Go 官方入门：https://go.dev/doc/tutorial/getting-started
- Go 官方文档入口：https://go.dev/doc/docs.html
- Go 数据库访问教程：https://go.dev/doc/tutorial/database-access

结合项目要能讲：

> Go API Service 作为后端主入口，每个请求都生成 request_id，并用 context timeout 控制 Redis、DB、Python Runtime 调用和工具执行。若 Python Runtime 超时，Go 不继续执行 action，避免状态写入不确定。

## 2. Gin / HTTP API / SSE

重点学习：

- Gin 路由、中间件、参数绑定、错误响应。
- HTTP handler 如何组织业务调用。
- SSE 的 `text/event-stream` 格式。
- 当前项目 SSE 事件顺序：`start -> delta* -> final`，错误事件为 `error`。

资料：

- Gin Quickstart：https://gin-gonic.com/en/docs/quickstart/
- WHATWG Server-Sent Events：https://html.spec.whatwg.org/dev/server-sent-events.html
- MDN Server-sent events：https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

对应源码：

- `app/api/chat.py`
- `app/services/chat_service.py`
- `clients/qt-debug-console/src/api/SseEventParser.*`

结合项目要能讲：

> 同步聊天和流式聊天共用同一条业务链路，只是 transport 不同。SSE 路径保持 `start -> delta* -> final`，这样 Qt Debug Console 不需要大改。第一版可以让 Python 一次性返回完整 reply，由 Go 切分成 delta 输出；后续再升级为 Python 真 token streaming。

## 3. DB / Redis

重点学习：

- Go DB 连接池、事务、索引、repository 层。
- SQLite 和 MySQL/PostgreSQL 在并发、部署、查询能力上的差异。
- Redis 用于短期记忆、限流、缓存。
- 如何按 `player_id`、`npc_id`、`world_id`、`status` 建索引。

资料：

- GORM 文档：https://gorm.io/docs/
- go-redis 文档：https://redis.io/docs/latest/integrate/go-redis/
- PostgreSQL 索引文档：https://www.postgresql.org/docs/current/indexes.html

对应源码：

- `app/services/game_service.py`
- `app/repositories/player_state_repository.py`
- `app/repositories/shared_knowledge_repository.py`
- `app/services/redis_memory_service.py`

结合项目要能讲：

> 原项目 SQLite 把玩家状态中的背包、任务、关系、world flag 等复杂字段以 JSON 存储，适合 demo，但不利于并发写和结构化查询。改造后 Go 侧用 MySQL/PostgreSQL 保存玩家、背包、任务、任务目标、关系和 world flag，并成为玩家状态唯一写入口。Python 只产出 action，不直接写状态。

## 4. ToolService / 状态机 / 幂等

这是项目里最值得重点讲的后端能力。

必须读懂：

- `app/services/tool_service.py`
- `app/services/world_action_service.py`
- `app/services/game_service.py`
- `tests/test_tool_service.py`
- `tests/test_world_action_service.py`

重点学习：

- 白名单工具执行。
- 参数校验。
- 幂等返回状态。
- 状态机验证。
- LLM action 和真实状态修改之间的隔离。

必须能解释的工具：

- `create_quest`
- `complete_quest`
- `add_item`
- `remove_item`
- `move_player`
- `update_relationship`
- `set_world_flag`
- `publish_knowledge`
- `mark_knowledge_known`
- `resolve_knowledge`

结合项目要能讲：

> LLM 输出不可信，不能让模型直接改数据库。模型只能返回结构化 `AgentAction`，Go 的 `ToolService` 负责白名单校验、参数校验和幂等执行。例如重复 `create_quest` 返回 `already_active`，重复 `add_item` 返回 `already_exists`。这样即使模型重复输出、请求重试或网络重放，也不会破坏玩家状态。

面试高频追问：

- LLM 返回非法工具怎么办？
- 同一个请求重复提交怎么办？
- 工具执行一半失败怎么办？
- 玩家只说“我完成任务了”，为什么不能直接完成？

回答核心：

> 自然语言只生成候选动作。真正推进任务的是 Go 侧状态机，它根据玩家位置、背包、任务目标、世界事件和工具执行结果判断动作是否成立。只声称完成任务不会修改任务状态。

## 5. Python Agent Runtime / LangGraph / Chroma

重点学习：

- LangGraph 的 graph / node / state / checkpoint。
- LangGraph streaming 和 persistence 的基本概念。
- Chroma 长期记忆检索。
- embedding 的作用。
- Prompt 构建和上下文预算。

资料：

- LangGraph Python 文档：https://docs.langchain.com/oss/python/langgraph
- LangGraph Persistence：https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Streaming：https://docs.langchain.com/oss/python/langgraph/streaming
- Chroma 文档：https://docs.trychroma.com/
- Chroma Embedding Functions：https://docs.trychroma.com/docs/embeddings/embedding-functions

对应源码：

- `app/core/llm.py`
- `app/services/context_builder_service.py`
- `app/services/long_term_memory_service.py`
- `app/services/reflection_worker.py`
- `app/agents/world_agent.py`
- `app/agents/quest_agent.py`

结合项目要能讲：

> Go 能做 Agent 和 Prompt，但当前项目已经在 Python 生态里跑通 LangGraph、Chroma、embedding 和 LLM 调用。为了降低重写成本，拆分后 Python Runtime 继续负责 Prompt 构建、长期记忆检索、LLM 调用和 LangGraph 编排，只通过内部接口返回 `reply/actions/context_report/prompt`，不直接修改玩家状态。

## 6. Docker / 可观测性 / 压测

重点学习：

- Docker Compose 一键启动多服务。
- Prometheus metrics。
- Go pprof。
- request_id 日志串联。
- 压测指标：QPS、P95、错误率、SSE 并发连接数。

资料：

- Docker Compose Quickstart：https://docs.docker.com/compose/gettingstarted/
- Prometheus Go instrumentation：https://prometheus.io/docs/guides/go-application/
- OpenTelemetry Go：https://opentelemetry.io/docs/languages/go/getting-started
- Go pprof：https://pkg.go.dev/net/http/pprof

结合项目要能讲：

> 本地通过 Docker Compose 启动 Go API、Python Agent Runtime、Redis 和 DB。Go 服务暴露 `/metrics` 和 pprof，用 request_id 串联 HTTP 请求、Python Runtime 调用、工具执行和 Trace 写入。压测时关注 QPS、P95 延迟、错误率和 SSE 并发连接数。

## 7. 推荐学习顺序

1. Go 基础和 Gin：能写 handler、middleware、HTTP client。
2. DB 和 Redis：能实现玩家状态 CRUD、短期记忆、限流。
3. 当前 ToolService / WorldActionService：理解迁移核心。
4. SSE：能讲清楚流式响应协议和客户端兼容性。
5. LangGraph / Chroma：能解释 Python Runtime 为什么保留。
6. Docker / metrics / pprof / 压测：补齐工程化表达。

## 8. 最终必须能讲出的完整链路

准备并背熟这段：

> 用户从 Qt 客户端发送聊天请求到 Go API Service。Go 生成 request_id，做限流、参数校验和超时控制，然后读取玩家状态、Redis 短期记忆和共享情报，再调用 Python Agent Runtime。Python 负责 Prompt 构建、长期记忆检索、LLM 调用和 LangGraph 编排，返回 reply 和 actions。Go 收到 actions 后通过 ToolService 白名单和状态机执行，写入 DB、Redis 和 Trace。SSE 场景下 Go 按 `start -> delta -> final` 推送给客户端，保证流式体验和最终状态一致。

## 9. 面试讲法模板

### 为什么拆成 Go + Python？

> 原来的 FastAPI 单体同时负责 API、状态、记忆、工具执行、LLM 和 Agent 编排，功能能跑，但工程边界不清晰。拆分后 Go 负责确定性的后端主链路，包括 API、状态、工具、Redis、DB、SSE、Trace 和可观测性；Python 负责 AI 生态更成熟的部分，包括 LangGraph、Chroma、embedding 和 LLM 调用。这样既保留 AI 能力，又增强后端工程化。

### 为什么 LLM 不直接改状态？

> LLM 输出具有不确定性，可能重复、遗漏参数或生成非法工具。如果让它直接写 DB，会导致状态不可控。项目中 LLM 只能返回结构化 action，Go 侧 ToolService 做白名单和参数校验，WorldActionService 做状态机验证，最终只有合法且可验证的动作才能修改玩家状态。

### SSE 怎么保证最终状态一致？

> SSE 只是传输方式，不改变业务链路。Go 先发送 `start`，再发送 `delta`，结束时执行工具、写记忆和 Trace，最后发送 `final`。客户端以 `final` 作为最终状态依据，避免只看到流式文本但状态未落库。

### Python Runtime 失败怎么办？

> Go 调用 Python Runtime 时有 context timeout。如果超时或返回非法结构，Go 不执行工具，写入错误 Trace，并返回明确错误或 fallback reply。这样失败不会造成半写状态。

## 10. 配套文档

- 改造计划：`docs/go_python_backend_split_plan.md`
- 当前项目状态：`docs/current_project_record.md`
- 接手总览：`docs/project_handoff_overview.md`
- 后端生命周期：`docs/backend_lifecycle.md`
- 面试问答：`docs/interview_qa_full.md`

