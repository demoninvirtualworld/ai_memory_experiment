
# Copilot / AI agent instructions for ai_memory_experiment

**Purpose:** Enable AI coding agents to be productive immediately by providing actionable, project-specific context.

## Big Picture
- Flask-based experimental platform for simulating "AI memory" in human-AI interaction.
- `app.py`: main entrypoint, HTTP API, static serving, file-backed user/task storage under `data/users/`.
- `models.py`: data models (`User`, `Task`, `Document`, `ChatMessage`, `MemoryContext`), memory context logic for different memory group behaviors.
- `utils.py`: managers for LLM API (Qwen/DeepSeek), data, and memory orchestration.
- No database: all persistent data is JSON files in `data/users/` and related folders.

## Key Files & Responsibilities
- `app.py`: API routing, session/auth (`active_sessions`), task lifecycle, AI response simulation (`/api/ai/response`).
- `models.py`: memory group logic (`no_memory`, `short_memory`, `medium_memory`, `long_memory`), data shapes, context helpers.
- `utils.py`: LLM API wrappers, data access, memory context builder.
- `data/users/`: user JSON files (`<user_id>.json`), each with `task_set`, `conversation`, `document`, `questionnaire`, `experiment_phase`, etc.
- `static/index.html`: minimal frontend for manual testing.

## Developer Workflows
- **Run locally:** `python app.py` (listens on port 8000).
- **Install deps:** `pip install -r requirements.txt` (Flask, Flask-CORS).
- **Reset data:** POST `/api/debug/reset` (clears users, recreates admin `admin/psy2025`).
- **API auth:** Use `Authorization: Bearer <session_token>` header after login.
- **Default admin:** username `admin`, password `psy2025`.

## Project Conventions & Patterns
- User/task data is always file-based. If adding DB support, provide migration/compat.
- Timestamps: always ISO string (`datetime.now().isoformat()`).
- Passwords: SHA256 hash via `hash_password()` in `app.py`.
- `task_set` items: `task_id`, `conversation`, `questionnaire`, `document`, `submitted`, `submitted_at`.
- Conversation messages: dicts with `message_id`, `content`, `is_user`, `timestamp`.
- Task definitions: see `initialize_data()` in `app.py`—keep numeric order and phase mapping.
- Memory context: see `MemoryContext.get_context_for_task()` in `models.py` for group logic and helpers (`_conversation_to_text`, `_generate_conversation_summary`, `_truncate_to_tokens`).

## Integration & Extension
- LLM API: Qwen/DeepSeek, switch in `config.py` (`model_provider`).
- To add new memory behaviors, extend `MemoryContext` and update API logic.
- If user schema changes, update `create_default_admin()` and provide migration.

## Example API Usage
- Get current user: `GET /api/users/me` (auth required)
- Simulate AI reply: `POST /api/ai/response` with `{ "taskId": 2, "userMessage": "...", "responseStyle": "high" }`
- Inspect user file: `data/users/<username>.json`

## Gotchas
- `DATA_DIR` is relative to repo root; ensure correct path in tests/containers.
- Avoid large in-memory state in `active_sessions`—no persistence by default.
- Update `README.md` if run instructions or credentials change.

If you need more examples or clarification, request a specific scenario or file to be documented.
