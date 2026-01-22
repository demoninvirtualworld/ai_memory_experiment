# Copilot / AI agent instructions for ai_memory_experiment

Purpose: give an AI coding agent fast, actionable context so it can be productive immediately.

- Big picture:
  - This is a small Flask-based experimental platform that simulates an "AI memory" study.
  - `app.py` is the single entrypoint that defines the HTTP API, static serving, and simple file-backed storage under `data/users/`.
  - `models.py` contains higher-level data shapes and the `MemoryContext` logic used to build memory-aware prompts/summaries.

- Key files and responsibilities:
  - `app.py`: routing, auth/session management (`active_sessions`), task lifecycle, simulated AI responses (`/api/ai/response`). Primary place to change API behavior.
  - `models.py`: `User`, `Task`, `Document`, `ChatMessage`, and `MemoryContext`. Implementations show how memory variants (`no/short/medium/long`) are derived.
  - `data/users/`: persistent user JSON files; each file is named `<user_id>.json` and stores `task_set`, `conversation`, `document`, `questionnaire`, `experiment_phase`, etc.
  - `static/index.html`: the minimal frontend used during manual testing.

- Important runtime / dev workflows:
  - Start locally with: `python app.py` (the app listens on port 3000).
  - Dependencies are listed in `requirements.txt` (Flask, Flask-CORS). Use a virtualenv and `pip install -r requirements.txt`.
  - Debug helper: POST `/api/debug/reset` clears `data/users/` and recreates the default admin (`admin/psy2025`). Useful for tests.

- Auth and integration notes:
  - Sessions are in-memory in `app.py` variable `active_sessions`. API requests authenticate via header `Authorization: Bearer <session_token>`.
  - Example login flow: POST `/api/auth/login` -> returns `session_token`. Use that token for subsequent authenticated calls.
  - Default admin exists after startup: username `admin`, password `psy2025`. Admin endpoints check `user_type == 'admin'`.

- Data & patterns agents should preserve:
  - User storage is file-based (no DB). Any code changes that assume DBs should also include migration or a compatibility layer.
  - Task definitions are initialized in `initialize_data()` (in `app.py`). Editing tasks should keep the numeric `task_id` ordering and phases.
  - Conversation messages are dictionaries with keys: `message_id`, `content`, `is_user`, `timestamp`. Keep this shape when producing or parsing chat data.
  - `task_set` items include `task_id`, `conversation`, `questionnaire`, `document`, `submitted`, `submitted_at`.

- Memory behavior specifics (important for AI features):
  - `MemoryContext.get_context_for_task(...)` in `models.py` implements four behaviors:
    - `no_memory` -> empty context
    - `short_memory` -> last 1/3 of previous conversation for previous task
    - `medium_memory` -> generated summaries of previous tasks (simple extractive summary in code)
    - `long_memory` -> full combined history of earlier tasks (truncated by characters/tokens)
  - When updating or extending memory logic, follow existing helpers: `_conversation_to_text`, `_generate_conversation_summary`, `_truncate_to_tokens`.

- Small examples to use when writing or testing code:
  - Get current user: GET `/api/users/me` with header `Authorization: Bearer <token>`.
  - Simulate AI reply: POST `/api/ai/response` with JSON `{ "taskId": 2, "userMessage": "...", "responseStyle": "high" }` (authenticated).
  - Inspect user file: `data/users/<username>.json` to see `task_set` and `conversation` shapes.

- Conventions & gotchas to respect:
  - The code stores timestamps as ISO strings (`datetime.now().isoformat()`). Use consistent formatting.
  - Passwords stored as SHA256 hashes via `hash_password()` in `app.py`. Do not change hashing format without migrating existing files.
  - `app.py` assumes `DATA_DIR = 'data/users'` is relative to repo root. Tests or Docker containers should map working directory accordingly.
  - Avoid introducing long-running in-memory state (e.g., large lists in `active_sessions`) without adding persistence or cleanup — the repo relies on small-scale local testing.

- When you make changes:
  - Update `README.md` if you change run instructions or default credentials.
  - Add a short example (curl or requests snippet) demonstrating any new API behavior.
  - If you modify the user JSON schema, include a migration helper and update `create_default_admin()` to be backward-compatible.

If anything here is unclear or you'd like the document to include examples for a specific change (e.g., converting storage to SQLite, or integrating a real LLM), tell me which direction and I'll iterate the file.
