# Citadel Hermes Backend Work Log

Goal: wire Citadel chat to Hermes sessions, profiles, skills, and memory instead of talking directly to Ollama.

Initial scope:

- Add a backend Hermes client/router in Citadel.
- Expose Hermes profiles, sessions, skills, and health status.
- Add a Hermes-backed chat completion path compatible with Citadel/Open WebUI chat flow where practical.
- Keep EdgeTower untouched; use it only as API/reference behavior.

Resume note: inspect this file and `git status`, then continue from the latest checklist below.

## 2026-06-29 Follow-up

- Added Hermes profile/fallback selection in the Citadel chat model selector.
- Encoded optional Hermes fallback models as `hermes:<profile>#model=<fallback>` and routed them through Hermes `/api/chat/start`.
- Forwarded Citadel user, role, chat, folder, and workspace context to Hermes as `citadel_context`.
- Added Hermes session sync into the Citadel chat list by creating lightweight Hermes-backed chat rows.
- Hydrated Hermes-backed chat transcripts from `/api/session` when those chats are opened.
- Guarded sidebar sync so compact Hermes list rows update metadata without overwriting existing Citadel chat transcripts.

## Resume Here

Current state as of the stop request:

- Repo: `/home/edgesecure/Citadel`
- Branch: `main`
- Commit already created and pushed before the stop request landed: `62db2f4a0 Add Hermes backend integration`
- Working tree after the commit/push was clean before this note edit.
- Do not modify `/home/edgesecure/EdgeTower`; it was only used as the Hermes API reference.
- Do not commit or push additional work unless the human explicitly asks.

Files added:

- `backend/open_webui/utils/hermes.py`
- `backend/open_webui/routers/hermes.py`
- `docs/citadel-hermes-backend-work-log.md`

Files changed:

- `backend/open_webui/utils/models.py`
- `backend/open_webui/utils/chat.py`
- `backend/open_webui/main.py`

What the current backend slice does:

- Adds Hermes profile-backed virtual models named `hermes:<profile>`.
- Adds authenticated Citadel endpoints under `/api/v1/hermes` for status, profiles, sessions, and skills.
- Routes `owned_by == "hermes"` or `hermes:<profile>` chat completions through the Hermes backend.
- Creates or reuses a Hermes session per Citadel user/profile/chat key.
- Stores that mapping in `DATA_DIR/citadel_hermes_sessions.json`.
- Converts Hermes SSE events from `/api/chat/stream` into OpenAI-compatible chat completion chunks for Citadel/Open WebUI.

Verification already run:

- `python3 -m py_compile backend/open_webui/utils/hermes.py backend/open_webui/routers/hermes.py backend/open_webui/utils/models.py backend/open_webui/utils/chat.py backend/open_webui/main.py`
- `git diff --check`
- Local Hermes smoke test fetched health, 19 profiles, and 19 `hermes:<profile>` model entries.
- Local Hermes chat smoke test with `hermes:default` and prompt `Say OK only.` returned `OK`.

Recommended next steps:

- Review whether `CITADEL_HERMES_PASSWORD` is set in the Citadel service environment, not just the old Open WebUI/EdgeTower environment.
- Restart or create the Citadel service so it runs this repo instead of `/home/edgesecure/open-webui`.
- Open Citadel from LAN, refresh models, and confirm `Hermes / <profile>` options appear in the model picker.
- Send a Citadel UI chat through `hermes:default`, then a follow-up in the same chat, and confirm Hermes session continuity in `/api/v1/hermes/sessions`.
- Decide whether the UI should get a dedicated Hermes panel for sessions, skills, and memory, or whether the model-picker route is enough for the next installer phase.

## Checklist

- [x] Identify Citadel chat completion routing point.
- [x] Identify minimal Hermes WebUI HTTP contracts.
- [x] Add Citadel Hermes client configuration.
- [x] Add Citadel Hermes router/status endpoints.
- [x] Add Hermes-backed chat completion route or model pipe.
- [x] Verify with local Hermes service on `127.0.0.1:8787`.

## Implementation Notes

- Hermes profiles are exposed as Citadel model IDs using `hermes:<profile>`.
- Citadel routes Hermes model chat completions through `/api/session/new`, `/api/chat/start`, and `/api/chat/stream` on the Hermes backend.
- Citadel persists chat-to-Hermes session continuity in `DATA_DIR/citadel_hermes_sessions.json`.
- Configure Hermes connection with `CITADEL_HERMES_BASE_URL`, `CITADEL_HERMES_PASSWORD`, and `CITADEL_HERMES_TIMEOUT`.
- Smoke test passed against local Hermes: fetched health/profiles/models and completed a short `hermes:default` chat turn.
