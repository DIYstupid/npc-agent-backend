# Go + Python 后端拆分改造计划

更新时间：2026-05-23

## 0. 文档目的

本文给后续接手的 agent / 开发者使用，目标是把当前 `npc-agent-backend` 从 Python FastAPI 单体逐步改造成：

```text
Go API Service：后端主服务、API、状态、工具、Trace、Redis、DB、SSE
Python Agent Runtime：LLM / LangGraph / Chroma / embedding / Prompt 构建
```

核心原则：

- 先保留现有行为，再做服务拆分。
- 先搭 Go 框架和契约，再迁移业务模块。
- 先迁移确定性后端逻辑，暂不重写 LangGraph / Chroma / embedding。
- Qt Debug Console 的外部 API 尽量保持兼容，避免前后端同时大改。

## 1. 当前基线

当前项目是 Python FastAPI 后端，关键能力包括：

- `POST /chat/{npc_id}` 同步聊天。
- `POST /chat/{npc_id}/stream` SSE 流式聊天。
- `ChatPipeline` 三阶段：`start -> generate -> finalize`。
- `ToolService` 白名单工具和幂等执行。
- `GameService` + SQLite 玩家状态。
- `SharedKnowledgeService` + SQLite 共享情报。
- `LongTermMemoryService` + Chroma 长期记忆。
- `QuestAgent` / `WorldAgent` 基于 LangGraph。
- `TraceService` 持久化 Prompt Trace / Agent Trace。
- Redis 短期记忆可选，失败时 fallback 到内存。
- Qt Debug Console 依赖现有 HTTP / SSE 接口。

接手前建议先读：

- `docs/current_project_record.md`
- `docs/project_handoff_overview.md`
- `app/services/chat_pipeline.py`
- `app/services/tool_service.py`
- `app/services/world_action_service.py`
- `app/agents/world_agent.py`
- `clients/qt-debug-console/README.md`

## 2. 目标架构

目标拓扑：

```text
Qt Debug Console / Future Game Client
        |
        v
Go API Service
  - public HTTP API
  - SSE streaming
  - auth / rate limit / request timeout
  - player state / quest / inventory / world flags
  - tool whitelist and idempotent execution
  - shared knowledge ledger
  - short-term memory with Redis
  - trace persistence
  - metrics / pprof / structured logs
        |
        v
Python Agent Runtime
  - prompt/context construction
  - LLM call and structured action parsing
  - LangGraph QuestAgent / WorldAgent
  - Chroma long-term memory search
  - embedding
  - reflection worker
```

服务边界：

| 能力 | 初始归属 | 目标归属 | 说明 |
| --- | --- | --- | --- |
| 外部 API | Python | Go | Go 对 Qt / 客户端暴露兼容接口 |
| SSE | Python | Go | Go 接管流式传输和超时控制 |
| 玩家状态 | Python SQLite | Go + DB | 迁移到 MySQL/PostgreSQL |
| 工具执行 | Python | Go | 白名单、幂等、状态修改都放 Go |
| 共享情报 | Python SQLite | Go + DB | 结构化事件账本适合 Go |
| Trace | Python SQLite | Go + DB | 保留 prompt/context/action 等字段 |
| Redis 短期记忆 | Python | Go | Go 统一读写聊天短期上下文 |
| Prompt 构建 | Python | Python，后续可迁 Go | 第一阶段不动 |
| LLM 调用 | Python | Python | 保留 OpenAI-compatible / mock |
| LangGraph | Python | Python | 保留 QuestAgent / WorldAgent |
| Chroma / embedding | Python | Python | Go 不直接处理向量库 |

## 3. 推荐目录结构

建议在当前仓库内新增服务目录，先不移动原 Python 代码：

```text
npc-agent-backend/
  services/
    go-api/
      cmd/
        api/
          main.go
      internal/
        config/
        logger/
        http/
          middleware/
          handler/
          sse/
        domain/
          player/
          quest/
          tool/
          knowledge/
          chat/
          trace/
        repository/
          mysql/
          postgres/
        cache/
          redis/
        agentclient/
        observability/
      migrations/
      go.mod
      README.md
    agent-runtime/
      README.md
      # 初期可先指向现有 app/，后续再拆出 Python 内部服务
  app/
  tests/
  clients/
    qt-debug-console/
  deploy/
    docker-compose.yml
```

短期也可以不创建 `services/agent-runtime/`，先让 Go 调用当前 FastAPI 进程的内部接口。等 Go 主服务稳定后，再把 Python runtime 单独整理。

## 4. 分阶段实施计划

### Phase 0：冻结行为基线

目标：明确改造前系统行为，避免拆分后无法判断是否回归。

任务：

- 跑通当前 Python 后端测试：
  - `python -m compileall app tests scripts`
  - `python -m unittest discover -s tests -v`
  - `python scripts/eval_memory_behavior.py`
- 记录当前 API 清单和 Qt 客户端依赖的接口。
- 固化核心响应样例：
  - `/health`
  - `/npcs`
  - `/game/state/{player_id}`
  - `/chat/{npc_id}`
  - `/chat/{npc_id}/stream`
  - `/memory/long-term`
  - `/knowledge/events`
  - `/world/interactions`
  - `/debug/traces`
- 给 SSE 事件写契约说明：`start -> delta* -> final`，错误为 `error`。

验收标准：

- 当前 Python 测试通过。
- 有一份 API contract 样例文档或测试 fixture。
- 不修改业务行为。

### Phase 1：搭 Go API Service 框架

目标：先搭 Go 服务骨架，不迁业务。

任务：

- 新建 `services/go-api`。
- 初始化 Go module。
- 建立基础模块：
  - config：读取 env。
  - logger：结构化日志，包含 `request_id`。
  - middleware：recover、request id、access log、timeout。
  - health handler：`GET /health`。
  - agent client：调用 Python 服务的 HTTP client。
- Go 先实现轻量代理：
  - `/health` 返回 Go 自身状态。
  - 其他接口可先反向代理到 Python，保持 Qt 客户端可用。
- 增加 Docker Compose 草案：
  - go-api
  - python-agent-runtime
  - redis
  - db

推荐技术栈：

- 快速落地：`Gin + GORM + go-redis + MySQL/PostgreSQL`。
- 更偏工程：`chi/net/http + sqlc + pgx + PostgreSQL`。
- 应届项目优先完成度，推荐先用 `Gin + GORM`。

验收标准：

- `go test ./...` 通过。
- `GET /health` 能区分 Go 服务和 Python runtime 状态。
- Qt 客户端仍可通过 Go 地址访问原有核心接口。

### Phase 2：迁移数据库和状态域模型

目标：Go 接管玩家状态、任务、背包、关系、world flag 的读写。

任务：

- 设计关系型表结构：
  - `players`
  - `player_inventory`
  - `player_quests`
  - `quest_objectives`
  - `player_relationships`
  - `player_world_flags`
- 从 `app/data/seed.py` 整理初始数据迁移脚本。
- Go 实现：
  - `PlayerRepository`
  - `PlayerService`
  - `QuestService`
  - `GET /game/state/{player_id}`
  - `GET /quest/{player_id}`
- 保持响应结构与当前 Pydantic schema 尽量一致。

设计注意：

- 不要把复杂 JSON 全部塞进单字段，除非为了第一版快速兼容。
- `quest_objectives` 建议结构化保存，后续查询和推进任务更清晰。
- 如果先求速度，可以第一版使用 JSON 字段，第二版再拆表。

验收标准：

- Go 侧 `/game/state/{player_id}` 与 Python 旧接口关键字段一致。
- 玩家状态相关单测覆盖：不存在玩家、背包、任务、关系、world flag。
- 不影响 Python Agent Runtime 读取玩家状态，必要时通过 Go 内部接口提供。

### Phase 3：迁移 ToolService 和 WorldActionService

目标：Go 接管“LLM 不能直接改状态，必须走白名单工具”的核心后端逻辑。

任务：

- 将 `app/services/tool_service.py` 行为迁移到 Go：
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
- 保留现有幂等状态：
  - `created`
  - `already_active`
  - `already_completed`
  - `added`
  - `already_exists`
  - `removed`
  - `not_found`
  - `not_allowed`
- 将 `WorldActionService` 状态机迁移到 Go：
  - `move`
  - `pick_item`
  - `use_item`
  - `submit_item_to_npc`
  - `defeat_enemy`
  - `talk_to_npc`
  - `inspect_object`
- 保留结构化调试接口：
  - `POST /world/actions`

验收标准：

- Go 单测覆盖每个工具的成功、重复执行、非法参数、玩家不存在。
- WorldAction 状态机能推进 quest objective。
- Python 不再直接修改玩家状态，状态修改统一经 Go。

### Phase 4：迁移共享情报和 Trace

目标：Go 接管共享情报账本和 Trace 持久化。

任务：

- 迁移 `KnowledgeEvent` 到 Go domain model。
- 新增表：
  - `knowledge_events`
  - `knowledge_event_players`
  - `knowledge_event_npcs`
  - `knowledge_event_tags`
- 实现接口：
  - `POST /knowledge/events`
  - `GET /knowledge/events`
  - `GET /knowledge/events/{event_id}`
  - `PATCH /knowledge/events/{event_id}`
  - `POST /knowledge/events/{event_id}/known-by/{npc_id}`
  - `POST /knowledge/events/{event_id}/resolve`
- 迁移 Trace：
  - `prompt_traces`
  - `agent_traces`
  - `GET /debug/traces`
  - `GET /debug/traces/latest`
  - `GET /debug/traces/{request_id}`

设计注意：

- Trace 字段允许 JSON 存储，因为 prompt、context report、actions 结构变化较快。
- KnowledgeEvent 的可见性建议结构化保存，方便按 player/npc 查询。

验收标准：

- 多 NPC 可见性规则与当前 Python 一致。
- 多玩家隔离测试通过。
- Qt Trace 面板仍能展示旧字段。

### Phase 5：Go 接管 Chat API 和 SSE

目标：Go 成为聊天主入口，Python 只负责生成 reply/actions/context。

Go 聊天链路：

```text
1. 接收 /chat/{npc_id} 或 /chat/{npc_id}/stream
2. 校验 npc_id / player_id / message
3. 读取玩家状态
4. 读取 Redis 短期记忆和 summary
5. 查询 Go 侧共享情报
6. 调用 Python Agent Runtime 生成 reply/actions/context_report
7. Go ToolService 执行 actions
8. 写短期记忆
9. 写 Trace
10. 返回 JSON 或 SSE final
```

Python 内部接口建议：

```text
POST /internal/agent/chat-generate
```

请求示例：

```json
{
  "request_id": "uuid",
  "npc_id": "blacksmith_001",
  "player_id": "player_001",
  "npc": {},
  "player_state": {},
  "message": "我想修剑",
  "short_term_memory": [],
  "summary_memory": "",
  "shared_knowledge": []
}
```

响应示例：

```json
{
  "reply": "这把剑损坏得很严重。要修好它，我需要一块银矿石。",
  "actions": [],
  "context_report": {},
  "prompt": "...",
  "selected_short_term_memory": [],
  "selected_long_term_memory": [],
  "selected_shared_knowledge": [],
  "summary_memory": "",
  "error": null
}
```

SSE 策略：

- 第一版：Python 一次性返回完整 reply，Go 按字符或小 chunk 输出 `delta`，最后输出 `final`。
- 第二版：Python 支持内部流式生成，Go 透传 token，同时仍在结束后执行 actions 和写 trace。

验收标准：

- `/chat/{npc_id}` 和 `/chat/{npc_id}/stream` 返回结构与当前客户端兼容。
- SSE 事件顺序仍是 `start -> delta* -> final`。
- 工具执行和状态修改发生在 Go。
- Trace 中能看到 prompt、context report、actions、executed_actions。

### Phase 6：整理 Python Agent Runtime

目标：把 Python 从 public API 后端收敛为内部 AI runtime。

任务：

- 保留或新增内部路由：
  - `/internal/agent/chat-generate`
  - `/internal/agent/world-interact`
  - `/internal/agent/quest-run`
  - `/internal/memory/long-term/search`
  - `/internal/memory/long-term/write`
- 将不再对外暴露的 FastAPI router 标记 deprecated，避免 Qt 继续直接依赖 Python。
- 保留 Python 测试，新增 contract test，验证 Go 请求 Python 的 JSON schema。
- 保留 `LLM_PROVIDER=mock`，方便离线测试。

验收标准：

- Go 不需要直接 import Python，也不访问 Python SQLite 状态库。
- Python runtime 可以独立启动、独立测试。
- 内部接口失败时 Go 有超时、重试或明确错误返回。

### Phase 7：工程化增强

目标：把项目从“功能 demo”提升为更像真实后端服务的工程项目。

任务：

- Redis：
  - 短期记忆。
  - 滑动窗口限流。
  - 可选分布式锁。
- DB：
  - migrations。
  - 索引。
  - 连接池配置。
- 可观测性：
  - structured logs。
  - Prometheus `/metrics`。
  - pprof。
  - request_id 贯穿 Go 和 Python。
- 稳定性：
  - context timeout。
  - Python runtime 熔断或降级。
  - LLM 失败 fallback。
- 压测：
  - `k6` 或 `wrk`。
  - 记录 QPS、P95、错误率、SSE 并发连接数。
- CI：
  - Go test。
  - Python unittest。
  - contract test。

验收标准：

- 一条命令启动本地依赖。
- 有压测脚本和结果记录。
- 有面向简历的架构图和关键指标。

## 5. Go 和 Python 的接口契约

建议所有 Go -> Python 内部调用都带：

- `request_id`
- `deadline_ms` 或由 Go context timeout 控制。
- `player_id`
- `npc_id`
- `world_id`
- `debug` 标记。

错误响应统一：

```json
{
  "error": {
    "code": "agent_runtime_unavailable",
    "message": "python agent runtime request timed out",
    "retryable": true
  }
}
```

Go 侧处理原则：

- Python 超时：返回明确错误，不执行工具。
- Python 返回非法 action：标记 `not_allowed` 或 `invalid_action`，不修改状态。
- Python 返回部分字段缺失：写 error trace，返回 fallback reply。
- Go 执行工具失败：reply 可以返回，但 `executed_actions` 必须反映失败原因。

## 6. 数据迁移建议

当前 SQLite 文件在 `app/data/`，不要直接把 runtime 数据当正式数据源。

建议顺序：

1. 先从 `app/data/seed.py` 生成 Go 侧 seed。
2. 开发环境新建空 DB。
3. 写一次性迁移脚本读取 SQLite：
   - player states
   - shared knowledge
   - traces
4. 迁移脚本只用于本地 demo，不作为生产依赖。

第一版可以允许 Python 和 Go 各自使用自己的测试数据，但一旦进入 Phase 3，玩家状态必须只有 Go 一个写入口。

## 7. 测试策略

Go 测试：

- domain service 单测：工具、任务、共享情报、世界行动。
- repository 集成测试：可用 test DB 或 sqlite fallback。
- handler 测试：HTTP status、JSON schema、错误响应。
- SSE 测试：事件顺序和 final payload。

Python 测试：

- 保留当前 unittest。
- 新增 internal runtime contract test。
- mock LLM 保持默认可用。

端到端测试：

- Go API -> Python runtime -> Go ToolService -> DB -> Trace。
- Qt 客户端核心操作手动验证：
  - 聊天。
  - 流式聊天。
  - 玩家状态刷新。
  - 长期记忆。
  - Trace 列表和详情。
  - World Interaction。

## 8. 风险和决策点

主要风险：

- 过早全量重写会拖慢进度。
- Go 和 Python 同时写玩家状态会造成数据不一致。
- SSE 流式如果先追求真 token 流，会增加跨服务复杂度。
- Qt 客户端接口一旦变更，需要同步改 C++，成本较高。

建议决策：

- 第一版优先兼容现有外部 API。
- 第一版 Go SSE 可以由完整 reply 模拟 delta，不必马上做 Python token streaming。
- `ToolService` 和 `WorldActionService` 迁移后，Python 只产出 action，不执行 action。
- Prompt 构建先留 Python；等 Go 主链路稳定后，再评估是否迁移 `ContextBuilderService`。

## 9. 后续 agent 接手清单

开始前：

- 读 `docs/current_project_record.md` 和本文档。
- 跑当前 Python 测试。
- 确认是否已有 `services/go-api`。
- 确认 Qt Debug Console 当前连接哪个 base URL。

每完成一个 Phase：

- 更新本文档对应阶段状态。
- 记录新增命令和测试结果。
- 如果改了 API，更新 Qt 客户端 README 或 API contract。
- 如果引入 DB schema，补 migration 和 seed 说明。

不要做：

- 不要直接删除现有 Python public API。
- 不要让 Go 和 Python 同时写同一份玩家状态。
- 不要把真实 `.env` key 写入文档。
- 不要把 `app/data/*.db` 或 Chroma runtime 数据作为代码提交。

## 10. 简历叙述目标

改造完成后可以表述为：

> 基于 Go + Python 重构 AI NPC Agent 后端，将原 FastAPI 单体拆分为 Go API Service 与 Python Agent Runtime。Go 侧负责 HTTP/SSE 接入、玩家状态、任务推进、工具幂等执行、共享情报、Redis 短期记忆、Trace 持久化、限流和可观测性；Python 侧负责 Prompt 构建、LLM 调用、LangGraph Agent、Chroma 长期记忆和 embedding。通过服务拆分、数据库结构化、Redis 限流、请求超时和压测提升系统工程化能力。
