# Repository Guidelines

## Project Structure & Module Organization

This is a Python FastAPI backend for NPC dialogue, game state, memory, and tool execution. The application entry point is `app/main.py`. Route modules live in `app/api/`, shared wiring and settings in `app/core/`, Pydantic request/response models in `app/schemas/`, business logic in `app/services/`, and persistence code in `app/repositories/`. Seed data and local persistence are under `app/data/`, including SQLite and Chroma files. Treat generated files such as `__pycache__/`, `app/data/*.db`, and `app/data/chroma/` as local runtime artifacts.

## Build, Test, and Development Commands

Create an environment and install runtime dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API locally:

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger docs. Use `python -m compileall app tests scripts` as a syntax smoke test.

## Coding Style & Naming Conventions

Use 4-space indentation, type hints, and small functions with explicit return types where practical. Keep module names and functions in `snake_case`, classes and Pydantic models in `PascalCase`, and constants in `UPPER_SNAKE_CASE`. Put API transport shapes in `app/schemas/`, endpoint logic in `app/api/`, and reusable behavior in `app/services/`. Prefer dependency wiring through `app/core/dependencies.py` rather than constructing shared services inside route handlers.

## Testing Guidelines

Tests live under `tests/` and currently use standard-library `unittest` to avoid extra dev dependencies. Name files `test_<module>.py` and methods `test_<behavior>()`. For API coverage, use FastAPI `TestClient`; for service coverage, mock external LLM, Redis, and Chroma dependencies so tests remain deterministic. Run tests with:

```powershell
python -m unittest discover -s tests -v
python scripts/eval_memory_behavior.py
```

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout, so no existing commit convention can be inferred. Use concise, imperative commit subjects, optionally scoped, such as `api: add chat history endpoint`. Pull requests should include a short summary, behavior changes, configuration or migration notes, linked issues, and test results. Include screenshots only for API docs or client-visible behavior changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local settings, but do not commit secrets or real API keys. Keep `LLM_PROVIDER=mock` or mock clients in tests. Local SQLite, Chroma, and memory data may contain player conversations; avoid including runtime data in reviews unless it is intentionally sanitized.
