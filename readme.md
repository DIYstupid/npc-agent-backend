# NPC Agent Backend

面向游戏 NPC 的 AI Agent 应用项目，包含 **Python FastAPI 后端** 和
**C++/Qt 调试面板**。后端负责 NPC 对话、记忆、RAG、工具调用、世界状态更新
和调试 Trace；Qt 面板用于查看流式聊天、上下文、Actions、Trace 和 Memory。

项目定位是展示 AI 应用工程能力和 C++/Qt 客户端能力，而不是堆叠多语言服务。

## 特点

- **Agent 对话管线**：同步聊天和 SSE 流式聊天共用 `ChatPipeline`，支持
  `start -> delta* -> final` 的流式响应。
- **记忆系统**：短期记忆支持 Redis / 内存 fallback，长期记忆使用 Chroma
  向量检索，并支持摘要记忆。
- **RAG 知识库**：支持 Markdown/TXT 文档导入、切分、检索、引用和注入 Prompt。
- **工具调用与世界状态**：通过工具白名单和状态机执行任务推进、物品变化、
  关系变化、世界事件等动作。
- **可观测性**：记录 Prompt Trace、上下文报告、token 预算、actions 和执行结果，
  便于调试 Agent 决策过程。
- **Qt Debug Console**：C++/Qt 桌面客户端，支持后端健康检查、NPC 列表、聊天、
  SSE、Trace、Memory、Context、Actions 等调试视图。
- **工程化**：提供 Docker Compose、本地测试、行为评测和轻量压测脚本。

## 如何运行

### 1. Docker Compose

默认使用 mock LLM，不需要真实 API key：

```powershell
docker compose up --build
```

服务地址：

- FastAPI 后端：`http://127.0.0.1:8000`
- Swagger 文档：`http://127.0.0.1:8000/docs`
- Redis：`127.0.0.1:16379`
- PostgreSQL：`127.0.0.1:15432`

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

### 2. 本地 Python 后端

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

如果不安装 `requirements-ml.txt`，服务仍可启动，RAG 和长期记忆会使用 hash
embedding fallback。

### 3. Qt Debug Console

Qt 客户端默认连接：

```text
http://127.0.0.1:8000
```

构建和测试说明见：

[clients/qt-debug-console/README.md](clients/qt-debug-console/README.md)

## 测试与压测

运行后端单元测试：

```powershell
python -m unittest discover -s tests -v
```

运行行为评测：

```powershell
python scripts/eval_memory_behavior.py
```

压测 chat 和 SSE 接口：

```powershell
python scripts/load_test_api.py --mode both --requests 40 --concurrency 8 --timeout-seconds 30
```

压测结果会写入：

- `eval/load_test_report.json`
- `eval/load_test_report.md`

报告文件默认不提交到 Git。

## 后续计划

- 补充 Qt 主界面和 Trace/Memory 面板截图。
- 整理面向 AI 应用岗位和 C++/Qt 客户端岗位的简历 bullet。
- 优化 Qt 调试面板的请求重放、日志查看和本地缓存能力。
- 增加更多 Agent 行为评测用例，覆盖 RAG 命中、工具调用准确率和状态一致性。
