# AI-NPC-Agent AI 应用与后端工程化改造计划

更新时间：2026-05-25

## 1. 改造目标

本项目后续同时服务两类投递方向：

- AI 应用开发：突出 RAG、Agent、Tool Use、Prompt Trace、评测和可展示 Demo。
- 后端开发：突出 Go API Service、HTTP/SSE、Redis、DB、限流、超时、日志、测试和部署。

目标架构：

```text
Qt Debug Console / Future Client
        |
        v
Go API Service
  - HTTP / SSE 统一入口
  - request_id / timeout / recover / access log
  - Redis 限流、缓存、短期记忆健康检查
  - 后续接管玩家状态、工具执行、Trace、DB 持久化
        |
        v
Python Agent Runtime
  - FastAPI 现有能力
  - LangGraph QuestAgent / WorldAgent
  - Chroma 长期记忆与 RAG 检索
  - Prompt 构建、LLM 调用、结构化 action 生成
```

改造原则：

- 先保留当前 Python 行为，再新增 Go 服务入口。
- Go 第一阶段只做后端工程骨架和代理，不急于重写业务。
- Python 保留 LangGraph、Chroma、embedding、Prompt 和 LLM 调用。
- LLM 不能直接修改状态，所有状态变更必须经过 ToolService / 状态机。
- 每个阶段都要有可运行命令、测试结果和简历可描述产出。

## 2. 当前项目基础

已有能力：

- FastAPI 聊天接口：`POST /chat/{npc_id}`。
- SSE 流式聊天：`POST /chat/{npc_id}/stream`，事件顺序为 `start -> delta* -> final`。
- `ChatPipeline` 三阶段链路：`start -> generate -> finalize`。
- Chroma 长期记忆、短期记忆、摘要记忆和 token budget 上下文装配。
- `ToolService` 白名单工具、参数校验和幂等执行。
- `WorldActionService` 世界行动状态机。
- `SharedKnowledgeService` 多 NPC 情报账本和多玩家隔离。
- `TraceService` 保存 prompt、context、actions、executed_actions。
- Qt Debug Console 展示 SSE、Trace 时间线和 token budget。
- Python 单元测试覆盖 chat、memory、rate limit、trace、tool、world action 等模块。

主要缺口：

- 缺少真正落地的 Go API Service。
- 缺少完整 RAG 知识库链路，当前更偏 NPC 长期记忆。
- 缺少 Agent/RAG 自动化评测报告。
- 缺少完整 Docker Compose、本地一键启动和部署说明。
- 缺少 Prometheus metrics、pprof、统一结构化日志等可观测性。
- 缺少面向简历和面试的架构图、Demo 场景和关键指标。

## 3. Phase 0：冻结当前基线

目标：确保后续改造不会破坏现有 Python 后端和 Qt 调试客户端行为。

任务：

- 跑通 Python 编译检查：
  ```bash
  python -m compileall app tests scripts
  ```
- 跑通 Python 单元测试：
  ```bash
  python -m unittest discover -s tests -v
  ```
- 跑通记忆行为评测：
  ```bash
  python scripts/eval_memory_behavior.py
  ```
- 新增或补全文档 `docs/api_contract.md`，记录核心接口：
  - `GET /health`
  - `GET /npcs`
  - `GET /game/state/{player_id}`
  - `POST /chat/{npc_id}`
  - `POST /chat/{npc_id}/stream`
  - `GET/POST /memory/long-term`
  - `GET/POST /knowledge/events`
  - `POST /world/interactions`
  - `GET /debug/traces`
- 固化 SSE 契约：
  - 正常：`start -> delta* -> final`
  - 异常：`error`

验收标准：

- Python 测试通过。
- API contract 中有请求样例、响应样例和错误样例。
- 不改动原有业务行为。

简历价值：

> 梳理并固化 AI Agent 后端 API/SSE 契约，建立回归测试基线，保障后续服务拆分过程中的接口兼容性。

## 4. Phase 1：新增 Go API Service MVP

目标：补齐后端语言与服务工程能力，让项目具备可运行的 Go 后端入口。

推荐目录：

```text
services/go-api/
  cmd/api/main.go
  internal/config/
  internal/logger/
  internal/http/
    handler/
    middleware/
    proxy/
  internal/agentclient/
  go.mod
  README.md
```

任务：

- 初始化 Go module。
- 使用 Gin 搭建 HTTP 服务。
- 实现 `GET /health`。
- 实现中间件：
  - recover
  - request_id
  - access log
  - timeout
- 实现 Python Agent Runtime HTTP client。
- 保留配置项：
  - `GO_API_ADDR`
  - `PYTHON_RUNTIME_BASE_URL`
  - `REQUEST_TIMEOUT_MS`
  - `REDIS_ADDR`
- 增加 Go 单元测试：
  ```bash
  go test ./...
  ```

验收标准：

- Go 服务可以独立启动。
- `/health` 返回 Go 服务状态和 Python runtime 配置状态。
- `go test ./...` 通过。

简历价值：

> 新增 Go API Service 作为 AI Agent 后端统一入口，封装 request_id、超时控制、异常恢复、访问日志和 Python Runtime 调用能力。

## 5. Phase 2：Go 代理 Python Chat / SSE

目标：让 Go 成为外部入口，同时保持现有 Python Agent 能力和 Qt 客户端兼容。

任务：

- Go 代理同步聊天：
  - `POST /chat/{npc_id}`
- Go 代理 SSE 聊天：
  - `POST /chat/{npc_id}/stream`
- Go 调用 Python 时透传或生成：
  - `request_id`
  - `player_id`
  - `npc_id`
  - `timeout`
- Python runtime 超时或失败时，Go 返回明确错误，不静默失败。
- SSE 第一版先透传 Python 输出，不急于做 token 级重组。

验收标准：

- 客户端访问 Go 地址也能完成聊天。
- SSE 事件顺序仍保持 `start -> delta* -> final`。
- Go access log 中可以看到 request_id、路径、状态码、耗时。

简历价值：

> 将 FastAPI AI Agent 能力接入 Go API Gateway，保持原有 HTTP/SSE 接口兼容，并通过 request_id 和 timeout 统一控制跨服务调用链路。

## 6. Phase 3：补完整 RAG 知识库链路

目标：把当前“长期记忆检索”升级为更贴近岗位要求的 RAG 应用能力。

任务：

- 新增文档导入接口或脚本：
  - Markdown
  - TXT
  - PDF 可作为后续增强
- 实现 chunk 切分：
  - 按标题层级切分
  - 按 token 上限切分
- 写入 Chroma：
  - `doc_id`
  - `chunk_id`
  - `source`
  - `page`
  - `created_at`
- 检索增强：
  - 向量检索
  - 关键词过滤
  - metadata 过滤
  - 简单 rerank 或 score merge
- 回答中返回引用来源。
- 接入 `ContextBuilderService`，让 RAG chunk 进入 prompt 上下文。

验收标准：

- 可以导入一份项目知识库文档并完成问答。
- Trace 中能看到 selected RAG chunks。
- 回答结果能展示来源引用。

简历价值：

> 实现知识库 RAG 链路，支持文档切分、Embedding 入库、Chroma 检索、上下文重排和来源引用，并接入 Agent Prompt 构建流程。

## 7. Phase 4：Tool Use 契约与安全执行

目标：把现有 ToolService 包装成更符合大模型应用岗位表达的 Function Calling / Tool Use 能力。

任务：

- 为 `AgentAction` 定义 JSON Schema。
- 为每个工具定义参数 schema：
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
- 非法工具返回 `invalid_action` 或 `not_allowed`。
- 参数错误不修改状态。
- Tool 执行结果写入 Trace。
- 后续可增加最小 MCP demo，暴露部分工具给外部 Agent 调用。

验收标准：

- 非法 action 有测试覆盖。
- 重复 action 保持幂等。
- Trace 能展示 raw actions、validated actions、executed actions。

简历价值：

> 设计 Agent Tool Use 执行层，通过 JSON Schema、白名单校验、幂等状态码和状态机验证隔离 LLM 输出与真实状态修改。

## 8. Phase 5：Agent / RAG 自动化评测

目标：从“能跑”升级为“能衡量效果”。

任务：

- 新增测试集：
  ```text
  eval/agent_cases.jsonl
  ```
- 每条 case 包含：
  - player_id
  - npc_id
  - message
  - expected_tools
  - expected_knowledge_hit
  - expected_quest_state
- 新增评测脚本：
  ```text
  scripts/eval_agent_behavior.py
  ```
- 指标：
  - RAG 命中率
  - 工具调用正确率
  - 任务推进成功率
  - 平均延迟
  - P95 延迟
  - token 消耗
  - 错误率
- 输出：
  ```text
  eval/eval_report.md
  eval/eval_report.json
  ```

验收标准：

- 支持 mock LLM 离线评测。
- 评测报告可复现。
- 失败 case 能定位到 Trace。

简历价值：

> 构建 Agent 自动化评测体系，覆盖 RAG 命中率、工具调用正确率、任务完成率、响应延迟和 token 消耗，支持 mock LLM 离线回归。

## 9. Phase 6：后端工程化增强

目标：让项目更像真实后端服务，而不是单机 Demo。

任务：

- Redis：
  - 限流
  - 短期记忆缓存
  - 健康检查
- DB：
  - 后续接入 PostgreSQL 或 MySQL
  - 结构化玩家状态、任务、工具执行记录
  - migrations 和索引
- 可观测性：
  - structured logs
  - request_id 贯穿 Go 和 Python
  - `/metrics`
  - Go pprof
  - LLM 调用耗时
  - RAG 检索耗时
  - Tool 执行结果统计
- 部署：
  - `docker-compose.yml`
  - `.env.example`
  - 一条命令启动 Go、Python、Redis、DB

验收标准：

- 本地一条命令启动核心依赖。
- `/health` 能检查 Go、Python、Redis、DB。
- README 有启动命令、依赖说明和常见错误。

简历价值：

> 增加 Redis 限流、Docker Compose 部署、结构化日志、健康检查和基础 metrics，提升 AI Agent 后端的工程化和可维护性。

## 10. Phase 7：文档、Demo 与简历材料

目标：让项目在投递和面试中容易被理解。

任务：

- 更新 `readme.md`：
  - 项目简介
  - 架构图
  - 启动方式
  - Demo 场景
  - API 列表
  - 测试命令
- 增加 Demo 截图：
  - SSE 流式聊天
  - Trace 面板
  - RAG 来源引用
  - Tool 执行结果
- 增加面试讲解文档：
  - 为什么 Go + Python 拆分
  - 为什么 LLM 不能直接改状态
  - SSE 如何保证最终状态一致
  - Python Runtime 失败如何处理

验收标准：

- README 可以让陌生面试官 3 分钟看懂项目。
- 简历中 AI 应用版和后端版可以分别提炼。

AI 应用版简历表达：

> 基于 FastAPI + LangGraph 构建 AI NPC Agent 系统，支持 RAG 长期记忆、短期/摘要记忆、Tool Use、SSE 流式响应、Prompt Trace 和自动化评测。

后端版简历表达：

> 基于 Go + Python 对 AI Agent 后端进行服务拆分，Go 侧负责 HTTP/SSE 接入、request_id 链路追踪、超时控制、Redis 限流和 Python Agent Runtime 调用，Python 侧负责 LangGraph、Chroma、Prompt 构建和 LLM 调用。

## 11. 推荐执行顺序

短期投递优先级：

1. Phase 0：冻结基线。
2. Phase 1：新增 Go API Service MVP。
3. Phase 2：Go 代理 Python Chat / SSE。
4. Phase 7：补 README、架构图和 Demo 说明。
5. Phase 3：补 RAG 知识库链路。
6. Phase 5：补 Agent/RAG 自动化评测。
7. Phase 4：补 Tool Use JSON Schema 和 MCP demo。
8. Phase 6：补 Redis、DB、metrics、Docker Compose。

如果只投 AI 应用，优先 Phase 3、4、5、7。

如果同时投后端，优先 Phase 1、2、6、7。
