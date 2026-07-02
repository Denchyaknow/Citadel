# Citadel

EdgeSecure is forking this repo in the name of science.

Citadel is an EdgeSecure research fork of [Open WebUI](https://github.com/open-webui/open-webui) rebuilt around localized Hermes agents. It keeps the useful Open WebUI application base, then changes the chat, automation, status, branding, and navigation layers so Citadel can act as a LAN-accessible control surface for local agent profiles.

Fork source: https://github.com/Denchyaknow/Citadel

Upstream base: https://github.com/open-webui/open-webui

## What Citadel Is

Citadel is a self-hosted AI dashboard for local and private workflows. It is designed to sit between a user and a localized Hermes agent service:

- Citadel handles the browser UI, users, permissions, chat shell, saved chat rows, automations screens, and status dashboard.
- Hermes handles agent profiles, profile memory, profile-specific training, agent skills, tool execution, sessions, and cron-backed scheduled work.
- Local or configured model providers still supply model inference behind Hermes or through retained Open WebUI provider paths.

The goal is to let users work from a clean web app without bypassing Hermes. When a Hermes profile is selected, Citadel sends the user message and basic Citadel context to Hermes, then streams the Hermes response back through the normal chat UI.

## Codex Session Review

This README was updated after reviewing the last 10 local Codex sessions on this machine. The relevant sessions covered:

- Hermes WebUI LAN binding and service setup on port `8787`.
- EdgeTower fork workflow and upstream-sync rules used as reference for Citadel.
- Citadel fork creation from Open WebUI and LAN service setup.
- Citadel/Hermes backend adapter work.
- Citadel live service setup as `Citadel_Gates.service` on port `8080`.
- Sidebar and navigation changes, including hiding workspace/global search paths.
- Citadel rebrand, icon replacement, favicon/splash updates, and PascalCase display cleanup.
- Login screen personalization and recent-user picker.
- Hermes-backed automation and cron endpoint debugging.
- Status dashboard creation, layout fixes, route containment, and navigation fixes.
- README cleanup to make this repository stand on its own.

## New Citadel Features

### Hermes Agent Bridge

- Adds a Citadel backend client for Hermes.
- Adds authenticated Hermes proxy routes under `/api/v1/hermes`.
- Reads Hermes health, profiles, sessions, skills, and cron job data.
- Exposes Hermes profiles as virtual model ids such as `hermes:default`.
- Routes Hermes profile chats through Hermes instead of talking straight to Ollama or OpenAI-compatible providers.
- Converts Hermes streaming events into chat-completion style chunks that the existing UI can render.
- Stores Citadel-to-Hermes session continuity in `DATA_DIR/citadel_hermes_sessions.json`.
- Syncs Hermes sessions into Citadel as lightweight chat rows so users can reopen agent sessions from the Citadel chat list.

### Profile and Model Selection

- Replaces the normal model-first flow with a Hermes profile-first flow when Hermes profiles are available.
- Shows profile names in PascalCase.
- Avoids showing "Hermes" branding in normal frontend labels except where implementation docs need the term.
- Shows fallback model choices only when the selected profile advertises fallback providers.
- Keeps normal OpenAI/Ollama/function models available when Hermes profiles are not being used.

### Citadel Context Sent to Agents

Citadel sends rough context to Hermes so localized agents know where a request came from. The context is intentionally small and app-level:

- Source is marked as `citadel`.
- User identity metadata can include name, email, id, and role.
- Chat, folder, and workspace metadata can be included when available.
- Attachments can be forwarded when present.
- Optional fallback model choice can be passed through when selected.

Hermes remains responsible for memory, profile behavior, skills, tools, and agent execution.

### Hermes-Backed Automations

- Moves Citadel Automations onto Hermes cron jobs.
- Adds backend proxy support for list, create, edit, pause, resume, run, delete, and run-history actions.
- Uses Hermes profiles instead of generic model selection when creating automations.
- Stores automation origin metadata so Hermes can see which Citadel user created the work.
- Shows running, paused, scheduled, completed, and failed states.
- Shows last run, next run, run snippets, run content, filenames, and errors when Hermes provides them.
- Polls running jobs so the UI updates after a manual run.
- Removes Automations from the lower user menu and places it in the main sidebar.
- Fixes earlier endpoint mismatches between `/api/cron` and Hermes `/api/crons` routes.

### Status Dashboard

- Adds `/status` as a Citadel page.
- Adds `/api/v1/status/summary` for app telemetry.
- Adds sidebar navigation to Status.
- Shows system health: CPU, RAM, and disk.
- Shows skill usage gathered from Hermes usage files when available.
- Shows sessions, messages, input tokens, output tokens, total tokens, and estimated cost.
- Shows model breakdowns, token breakdowns, daily tokens, activity by day, and activity by hour.
- Supports global admin view and user-scoped non-admin view.
- Includes reorder controls for dashboard modules.
- Fixes layout containment so Status no longer overlays folder or chat pages.
- Fixes navigation so Status points to `/status` and chat/folder root stays usable.

### Branding and Personalization

- Renames the visible app identity from Open WebUI to Citadel.
- Adds `Citadel-Icon.png`.
- Updates app title, startup banner, app constants, manifests, favicon, splash assets, and connection error text.
- Replaces old Open WebUI icons in login, onboarding, sidebar, and missing-model/avatar contexts.
- Adds a single Citadel home button in the sidebar.
- Adds login background image personalization in user settings.
- Adds recent login users on the auth screen with username-style quick selection.
- Keeps user profile images where appropriate and uses user fallback images where that is clearer than the Citadel icon.

### Navigation and Feature Overrides

- Status, Chat, Notes, and Automations are prioritized in the sidebar.
- Workspace navigation is disabled in the Citadel sidebar constants.
- Global search navigation is disabled because it does not search Hermes memory directly and only sees synced chat rows.
- New Chat routes to `/chat` to keep folder navigation clean.
- Hermes-backed models are inserted before OpenAI and Ollama base models.
- Chat routing checks Hermes models before falling through to retained Open WebUI provider paths.
- OpenAI direct catch-all passthrough remains disabled by default unless explicitly enabled.
- Citadel can still use retained Open WebUI features, but the default workflow is the localized Hermes agent workflow.

### LAN Service Setup

- Citadel is intended to run on the LAN for local browser and phone access.
- The current machine uses a user service named `Citadel_Gates.service`.
- Citadel listens on port `8080`.
- Hermes listens separately on port `8787`.
- The old Open WebUI service was disabled during Citadel setup so Citadel owns port `8080`.

## Retained Open WebUI Features

Citadel is a fork, not a total rewrite. These Open WebUI capabilities are still part of the base unless explicitly hidden, disabled, or superseded by Citadel/Hermes behavior:

- Responsive web UI and progressive web app behavior.
- Local-first self-hosting model.
- Chat UI with markdown and LaTeX rendering.
- File upload and document-assisted chat features.
- Local RAG and document library foundations.
- Web search and webpage ingestion support where configured.
- Ollama and OpenAI-compatible provider support.
- Image generation and editing provider support where configured.
- Voice, STT, TTS, and call-related provider support where configured.
- User accounts, roles, permissions, groups, and admin settings.
- Notes, folders, tags, channels, calendar, and saved chats.
- Function/tool/plugin foundations from Open WebUI.
- SQLite/PostgreSQL-compatible data storage paths.
- Redis/WebSocket/session support from the upstream architecture.
- OAuth, LDAP, trusted-header auth, SCIM, and related enterprise auth foundations where configured.
- Cloud storage and file picker foundations where configured.
- OpenTelemetry/audit/logging foundations where configured.

Some of these retained features may not be exposed in Citadel navigation yet. Citadel intentionally keeps the default UI focused on local agent operation.

## Data Flow

Citadel reads and writes from these main sources:

- Citadel database: users, settings, chats, messages, permissions, token usage, and local app metadata.
- Hermes HTTP service: health, profiles, sessions, skills, cron jobs, cron runs, and streamed agent responses.
- Hermes home files: skill usage counters and cron data when exposed through Hermes or read locally for status summaries.
- Model providers: Ollama, OpenAI-compatible APIs, or profile fallback providers depending on configuration.

For Hermes chat:

1. User selects a Citadel profile option backed by a Hermes profile.
2. Citadel creates or reuses a mapped Hermes session for the user/profile/chat.
3. Citadel sends the latest user message, optional attachments, optional fallback model, and small Citadel context to Hermes.
4. Hermes starts the agent turn and returns a stream id.
5. Citadel reads the Hermes stream and sends it to the browser as normal chat output.
6. Citadel can sync Hermes sessions back into the chat list for reopening later.

For Hermes automations:

1. User creates or edits an automation in Citadel.
2. Citadel sends the job to the correct Hermes profile through Hermes cron endpoints.
3. Hermes owns scheduling and execution.
4. Citadel reads job status and run history for display.

## Configuration

Common Citadel/Hermes environment variables:

```bash
CITADEL_HERMES_BASE_URL=http://127.0.0.1:8787
CITADEL_HERMES_PASSWORD=
CITADEL_HERMES_TIMEOUT=600
CITADEL_HERMES_SYNC_TIMEOUT=8
HERMES_HOME=/home/edgesecure/.hermes
```

Notes:

- `CITADEL_HERMES_BASE_URL` points Citadel at the localized Hermes service.
- `CITADEL_HERMES_PASSWORD` should match Hermes if Hermes auth is enabled.
- `CITADEL_HERMES_TIMEOUT` controls longer chat/agent calls.
- `CITADEL_HERMES_SYNC_TIMEOUT` controls shorter sync/status calls.
- `HERMES_HOME` is optional, but helps the Status page find local Hermes usage files.
- Local chat-capable Ollama models on this stack include `ragstack-llm:latest` and `qwen3:8b`. Embedding models such as `ragstack-embed:latest` and `nomic-embed-text:latest` are vector/embedding-only and cannot be used for chat sessions.
- Hermes Hivemind profiles should use `model.provider=custom`, `model.default=ragstack-llm`, and `model.base_url=http://127.0.0.1:11434/v1`. Keep the Hermes profile default tagless even though Citadel and Ollama may list the served model as `ragstack-llm:latest`; Ollama resolves `ragstack-llm` to the `latest` alias.
- If a Hermes profile chat returns an agent error and Hermes logs mention `Unknown provider 'custom:ragstack-llm'` or a Codex `HTTP 404`, the profile likely has `model.default=ragstack-llm:latest`. Rerun the fixed Phase 13 profile provisioning or set that Hermes profile default to `ragstack-llm`.
- Citadel hides embedding-only Ollama models from the chat model list and discards stale Citadel-to-Hermes session mappings that still point at the old `ragstack-llm:latest` custom-provider session form. The old Hermes session is not deleted; Citadel creates a fresh fixed session for the chat.

Useful inherited Open WebUI variables still apply where relevant:

```bash
WEBUI_NAME=Citadel
OLLAMA_BASE_URL=http://127.0.0.1:11434
OPENAI_API_KEY=
ENABLE_OPENAI_API=true
ENABLE_OLLAMA_API=true
ENABLE_OPENAI_API_PASSTHROUGH=false
```

## Install Guide

### Prerequisites

- Python 3.11 or 3.12.
- Node.js 18 through 22.
- npm.
- Git.
- A reachable Hermes service for Citadel agent features.
- Ollama or OpenAI-compatible providers if your Hermes profiles or retained Open WebUI features use them.

### Clone

```bash
cd /home/edgesecure
git clone https://github.com/Denchyaknow/Citadel.git
cd Citadel
git remote add upstream https://github.com/open-webui/open-webui.git
git fetch upstream
```

If the repo is already cloned:

```bash
cd /home/edgesecure/Citadel
git fetch origin
git fetch upstream
```

### Local Source Install

```bash
cd /home/edgesecure/Citadel
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
npm install
npm run build
```

Run Citadel:

```bash
export CITADEL_HERMES_BASE_URL=http://127.0.0.1:8787
export CITADEL_HERMES_PASSWORD=''
open-webui serve
```

Open:

```text
http://127.0.0.1:8080
```

For LAN use, bind to all interfaces through your service or server command and visit the host IP from another device:

```text
http://<lan-ip>:8080
```

### Development UI Server

Use this only for frontend development:

```bash
cd /home/edgesecure/Citadel
npm run dev
```

The production-like Citadel service should use the built frontend. Do not leave the Vite dev server running as the main Citadel instance.

### User Systemd Service

Example user service for LAN hosting:

```ini
[Unit]
Description=Citadel Gates WebUI
Documentation=file:/home/edgesecure/Citadel/README.md
After=network-online.target

[Service]
WorkingDirectory=/home/edgesecure/Citadel/backend
Environment=PYTHONPATH=/home/edgesecure/Citadel/backend
Environment=CITADEL_HERMES_BASE_URL=http://127.0.0.1:8787
Environment=CITADEL_HERMES_TIMEOUT=600
Environment=CITADEL_HERMES_SYNC_TIMEOUT=8
Environment=HERMES_HOME=/home/edgesecure/.hermes
ExecStart=/home/edgesecure/Citadel/.venv/bin/python3 -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 --forwarded-allow-ips "*" --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

Install and start:

```bash
mkdir -p ~/.config/systemd/user
$EDITOR ~/.config/systemd/user/Citadel_Gates.service
systemctl --user daemon-reload
systemctl --user enable --now Citadel_Gates.service
loginctl enable-linger "$USER"
```

Check status:

```bash
systemctl --user status Citadel_Gates.service
curl http://127.0.0.1:8080/health
```

### Docker-Style Deployment

Use the upstream Open WebUI Docker pattern as the base, but build from this Citadel fork so the Hermes bridge and Citadel UI changes are present:

```yaml
services:
  citadel:
    build:
      context: .
      dockerfile: Dockerfile
    image: citadel:local
    ports:
      - "8080:8080"
    environment:
      WEBUI_NAME: Citadel
      CITADEL_HERMES_BASE_URL: http://host.docker.internal:8787
      CITADEL_HERMES_PASSWORD: ${CITADEL_HERMES_PASSWORD}
      CITADEL_HERMES_TIMEOUT: "600"
      CITADEL_HERMES_SYNC_TIMEOUT: "8"
    volumes:
      - open-webui:/app/backend/data
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: always
```

Make sure the container can reach Hermes at `CITADEL_HERMES_BASE_URL`. If Hermes runs on the Docker host, `host.docker.internal` with `host-gateway` is usually the simplest Linux setup.

## Updating

Pull Citadel fork updates:

```bash
cd /home/edgesecure/Citadel
git pull origin main
npm install
npm run build
source .venv/bin/activate
pip install -e .
systemctl --user restart Citadel_Gates.service
```

Check for upstream Open WebUI updates:

```bash
cd /home/edgesecure/Citadel
git fetch upstream
git log --oneline main..upstream/main
```

Merge upstream only when ready to resolve fork conflicts:

```bash
git checkout main
git merge upstream/main
npm install
npm run build
python3 -m py_compile backend/open_webui/utils/hermes.py backend/open_webui/routers/hermes.py backend/open_webui/routers/citadel_status.py
git diff --check
```

## Operational Checks

Check Citadel:

```bash
curl http://127.0.0.1:8080/health
systemctl --user status Citadel_Gates.service
```

Check Hermes from Citadel's host:

```bash
curl http://127.0.0.1:8787/health
```

Check Citadel's Hermes proxy after login with an API token:

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/api/v1/hermes/status
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/api/v1/hermes/profiles
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8080/api/v1/hermes/sessions
```

Sync Hermes sessions into Citadel:

```bash
curl -X POST -H "Authorization: Bearer <token>" http://127.0.0.1:8080/api/v1/hermes/sync
```

Check Status API:

```bash
curl -H "Authorization: Bearer <token>" "http://127.0.0.1:8080/api/v1/status/summary?days=30"
```

## Troubleshooting

### Hermes profiles do not appear

- Confirm Hermes is running.
- Confirm `CITADEL_HERMES_BASE_URL` is reachable from Citadel.
- Confirm `CITADEL_HERMES_PASSWORD` is correct if Hermes auth is enabled.
- Restart Citadel after environment changes.
- Refresh models in the UI.

### Chat bypasses Hermes

- Make sure the selected model id starts with `hermes:`.
- Make sure Hermes profiles are loading.
- Confirm `/api/v1/hermes/status` returns healthy data.
- Confirm Citadel was restarted after the Hermes backend integration was deployed.

### Automations return HTML or JSON parse errors

- Restart `Citadel_Gates.service` so the Hermes automation routes are loaded.
- Confirm the frontend was rebuilt with `npm run build`.
- Confirm the browser is hitting port `8080`, not a stale Vite dev server.
- Confirm Citadel routes use `/api/v1/automations/hermes/cron/...`.

### Status page returns non-JSON

- Restart Citadel so `/api/v1/status/summary` is loaded.
- Confirm the frontend route is `/status`.
- Confirm the backend route is reachable with an authenticated request.

### LAN access does not work

- Confirm Citadel is bound to `0.0.0.0`.
- Confirm the LAN IP and port are correct.
- Check firewall rules.
- Check router or access point client isolation.

## Attribution and License

This fork inherits the upstream Open WebUI licensing structure. See [LICENSE](./LICENSE), [LICENSE_HISTORY](./LICENSE_HISTORY), and [LICENSE_NOTICE](./LICENSE_NOTICE).
