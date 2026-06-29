# Citadel Hermes Backend Work Log

Goal: wire Citadel chat to Hermes sessions, profiles, skills, and memory instead of talking directly to Ollama.

Initial scope:

- Add a backend Hermes client/router in Citadel.
- Expose Hermes profiles, sessions, skills, and health status.
- Add a Hermes-backed chat completion path compatible with Citadel/Open WebUI chat flow where practical.
- Keep EdgeTower untouched; use it only as API/reference behavior.

Resume note: inspect this file and `git status`, then continue from the latest checklist below.

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
