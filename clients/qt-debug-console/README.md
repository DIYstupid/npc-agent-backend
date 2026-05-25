# Qt Debug Console

这是 AI NPC Agent 后端的 Qt C++ 调试客户端，定位是 Debug Console，不是普通聊天窗口。

## 当前界面

- API 地址、玩家 ID、NPC 选择
- 顶部异步请求状态：显示当前进行中的 API operation，并在关键请求期间禁用对应按钮
- 请求取消和超时：顶部可取消全部请求，对话区可取消慢速 `chat` / `debug_prompt` 请求
- 聊天流式响应：发送消息走 `POST /chat/{npc_id}/stream`，客户端按 SSE `delta` 事件逐字追加 NPC 回复，并在 `final` 事件后刷新 Context、Actions、Memory 和 Trace
- NPC 列表、玩家状态树、Summary Memory
- 对话窗口、发送消息、Debug Prompt、清空历史
- Context Report 指标表
- Token 预算进度条：显示当前上下文窗口 `estimated_prompt_tokens / token_budget`、百分比和节省 token
- 当前上下文窗口用量：短期记忆选中/裁剪、长期记忆选中/裁剪、是否使用 Summary
- Section Tokens 表：按 prompt section 展示 token 估算
- Debug Prompt 原文
- planned / executed actions 表
- 长期记忆列表、搜索、新增、更新、删除
- Prompt Trace 列表、选中联动详情、Trace Memory Hits、Trace 原始 JSON
- API 错误与状态面板
- 本地缓存：NPC、玩家状态、聊天历史、Summary、长期记忆列表/搜索、Trace 列表/详情会在自动切换时复用缓存，手动刷新和写操作后强制更新
- 本地配置持久化：API 地址、玩家 ID、选中 NPC、右侧 tab、主窗口布局、主分栏尺寸和 Memory 过滤输入会通过 `QSettings` 保存

## 对应后端接口

- `GET /health`
- `GET /npcs`
- `GET /game/state/{player_id}`
- `POST /chat/{npc_id}`
- `POST /chat/{npc_id}/stream`
- `GET /chat/history/{player_id}/{npc_id}`
- `DELETE /chat/history/{player_id}/{npc_id}`
- `POST /chat/{npc_id}/debug-prompt`
- `GET /memory/summary/{player_id}/{npc_id}`
- `GET /memory/long-term`
- `GET /memory/long-term/search`
- `POST /memory/long-term`
- `PATCH /memory/long-term/{memory_id}`
- `DELETE /memory/long-term/{memory_id}`
- `GET /debug/traces`
- `GET /debug/traces/latest`
- `GET /debug/traces/{request_id}`

## 依赖

- Qt 5 或 Qt 6
- Qt Widgets
- Qt Network
- Qt Test（仅启用单元测试时需要）
- CMake 3.16+
- C++17 编译器

## 代码结构

- `src/api/`：后端 HTTP API 封装，`ApiClient` 统一发出请求开始/结束信号。
- `src/api/SseEventParser.*`：增量解析 `text/event-stream` 数据帧，供聊天流式响应使用。
- `src/common/`：通用 JSON 格式化和表格展示辅助。
- `src/ui/`：主窗口、UI 布局、渲染逻辑、异步请求状态管理、本地缓存和配置持久化。

`MainWindow` 已按职责拆分为布局、动作回调、渲染和请求状态文件；`AsyncRequestTracker` 负责统计正在进行的 operation，并驱动按钮禁用和顶部状态文本。`ClientCache` 负责短 TTL 的面板数据缓存，避免 NPC/面板来回切换时重复请求。`ClientSettings` 负责把客户端连接信息、窗口布局和常用筛选输入保存到本机配置。

默认请求超时：普通 API 15 秒，`chat` 90 秒，`debug_prompt` 60 秒。

## 聊天流式响应

客户端聊天发送默认使用 SSE endpoint：

```text
POST /chat/{npc_id}/stream
Accept: text/event-stream
```

后端事件约定：

```text
event: start
data: {"request_id":"...","npc_id":"...","player_id":"..."}

event: delta
data: {"text":"你"}

event: final
data: {"npc_id":"...","player_id":"...","reply":"你好...","actions":[],"executed_actions":[],"context_report":{...}}

event: error
data: {"request_id":"...","message":"..."}
```

客户端只把 `delta.text` 追加到正在显示的 NPC 消息；`final` 仍复用完整 `ChatResponse` 更新调试面板和本地缓存。取消聊天时仍使用同一个 `chat` operation，底层会 abort 当前 SSE `QNetworkReply`。

## 后续编译命令

等你确认要编译时，可以在本目录执行：

```powershell
cmake -S . -B build
cmake --build build --config Release
```

如果 Qt 没在默认路径，需要额外指定 `CMAKE_PREFIX_PATH`，例如：

```powershell
cmake -S . -B build -DCMAKE_PREFIX_PATH="D:\Qt\6.6.0\msvc2019_64"
```

## 单元测试

单元测试默认不参与普通客户端构建。需要测试时，在本目录开启 `BUILD_QT_CLIENT_TESTS`：

```powershell
cmake -S . -B build-tests -DBUILD_QT_CLIENT_TESTS=ON
cmake --build build-tests --config Release
ctest --test-dir build-tests --output-on-failure
```

如果使用 Visual Studio 等多配置生成器，运行测试时可指定配置：

```powershell
ctest --test-dir build-tests -C Release --output-on-failure
```

当前测试覆盖：

- `ClientSettingsTests`：空配置默认值、连接和布局字段回写、空 API/玩家字段归一化。
- `ClientCacheTests`：缓存读取、TTL 过期、单 key 和前缀失效。
- `AsyncRequestTrackerTests`：并发 operation 计数、状态文本、异常 finish 忽略。
- `SseEventParserTests`：SSE 分块、CRLF、多行 data 和无结尾分隔符的解析。

## 使用前准备

先启动后端：

```powershell
uvicorn app.main:app --reload
```

客户端默认连接：

```text
http://127.0.0.1:8000
```

默认玩家 ID：

```text
player_001
```

## 下一步可做

- Trace 列表自动刷新和刷新间隔配置
- 选中 Trace 后高亮 Context / Actions / Memory 的变化差异
- Memory 编辑区增加类型下拉、标签快捷选择和删除确认
- world event / quest 专用调试面板

## Phase 3 UI additions

- Dark QSS theme is packaged through `resources/resources.qrc` and loaded at startup.
- Context, Actions, Memory, Trace, and Status panels are now `QDockWidget` panels, so they can be rearranged, floated, hidden, and restored by `QSettings`.
- Trace view includes a custom `TraceTimelineWidget` that paints recent trace events and emits selection changes to the existing trace detail flow.
- Memory view includes a `QStyledItemDelegate` card renderer, memory type combo boxes, and delete confirmation.
- Custom UI code lives in `src/ui/widgets/`.
