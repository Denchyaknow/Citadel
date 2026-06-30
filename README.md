# Citadel - EdgeSecure Research Fork

EdgeSecure is forking this repo in the name of science.

Citadel is an EdgeSecure-maintained research fork of [Open WebUI](https://github.com/open-webui/open-webui). The original upstream README is preserved below this section so the base project context, license notes, and general Open WebUI installation material stay intact. This top section documents the Citadel-specific changes added in the latest local commits.

Upstream source: https://github.com/open-webui/open-webui

Current fork source: https://github.com/Denchyaknow/Citadel

---

## Citadel Overview

Citadel keeps the Open WebUI application foundation but bends the chat, automation, status, and branding layers toward EdgeSecure's localized Hermes agent environment. In practice, Citadel behaves like a local operator console: users interact with familiar chat and automation screens, while selected conversations and scheduled work are handed off to Hermes profiles running on the local network or host.

The intent is not to expose every Hermes implementation detail in the UI. Citadel shows profiles, sessions, automations, status, and useful activity telemetry, then sends user requests and context to Hermes through a backend bridge.

## Latest EdgeSecure Changes

### Hermes agent integration

- Added a backend Hermes client and router.
- Added authenticated Citadel endpoints under `/api/v1/hermes` for health, profiles, sessions, sync, skills, and Hermes cron job operations.
- Exposes Hermes profiles as virtual Citadel models named like `hermes:<profile>`.
- Gives the model selector a Hermes profile picker and optional fallback model selector when a Hermes profile advertises fallback providers.
- Routes chats for Hermes-owned models through Hermes instead of sending them directly to Ollama or an OpenAI-compatible provider.
- Converts Hermes streaming responses back into OpenAI-compatible chat chunks so the existing chat UI can render them normally.
- Stores Citadel chat to Hermes session continuity in `DATA_DIR/citadel_hermes_sessions.json`.
- Syncs Hermes session records into the Citadel chat list as lightweight chat rows so prior Hermes sessions can be reopened from Citadel.

### Localized Hermes data flow

At a high level, Citadel gets data from three places:

- Citadel's own database for users, chats, messages, tokens, costs, and app settings.
- The localized Hermes service for agent profiles, active sessions, skills, cron jobs, and streamed agent responses.
- Local host or Hermes usage files for status dashboard details such as CPU, memory, disk, and skill usage counters.

When a user selects a Hermes profile and sends a chat message, Citadel creates or reuses a Hermes session for that user/profile/chat combination. Citadel sends the latest user message, selected profile, optional fallback model, attachments when present, and a small `citadel_context` block that identifies the source as Citadel and includes user/chat/folder/workspace metadata. Hermes returns a stream id, Citadel reads the Hermes stream, and the response is delivered back to the browser through the normal chat streaming path.

This keeps Citadel responsible for the web app and user workflow while Hermes remains responsible for localized agent behavior, profile selection, memory, skills, and tool execution.

### Hermes-backed automations

- Reworked the automations API client to use Hermes cron jobs.
- Added backend proxy routes for listing, creating, editing, pausing, resuming, triggering, deleting, and inspecting Hermes cron jobs.
- Added profile-aware automation records so scheduled work belongs to a Hermes profile.
- Added run history support with status, run previews, filenames, errors, and running-state refresh.
- Updated automation filters to include running and completed states.
- Preserved the Citadel permission checks around automations before allowing access to Hermes-backed job controls.

### Status dashboard

- Added a new Citadel status route at `/status`.
- Added a backend summary endpoint at `/api/v1/status/summary`.
- Shows system health, skill usage, session counts, message counts, token totals, estimated costs, daily token activity, model breakdowns, and activity by day/hour.
- Supports user-scoped data for normal users and global data for admins.
- Handles non-JSON or stale backend responses with clearer restart guidance.
- Keeps the status page inside the main app layout and points sidebar navigation to the route.

### Citadel rebrand and personalization

- Changed default app identity from Open WebUI to Citadel.
- Updated backend title, startup banner, app constants, favicon/splash assets, and server connection error text.
- Added Citadel icon assets.
- Updated auth and sidebar presentation around the Citadel identity.
- Added login background image personalization stored through user settings/local browser storage.
- Added recent-login user shortcuts on the auth screen.
- Updated model display naming so Hermes profile names are shown cleanly.

### Navigation and feature overrides

Citadel keeps most Open WebUI capability available, but a few pieces are intentionally overridden or hidden for this fork's current workflow:

- Hermes-backed models are inserted ahead of OpenAI and Ollama models in the model list.
- Chat routing checks Hermes models before falling through to Ollama/OpenAI-compatible routing.
- Sidebar defaults now prioritize Chat, Status, Notes, and Automations.
- Workspace navigation is disabled in the Citadel sidebar constants for now.
- Global search navigation is disabled in the Citadel sidebar constants for now.
- The new chat path is pointed at `/chat` so folder navigation and the chat root behave cleanly.
- OpenAI direct catch-all passthrough remains disabled by default unless `ENABLE_OPENAI_API_PASSTHROUGH=True` is set.
- OpenRouter request title branding now identifies the app as Citadel.

## Configuration

Citadel expects a localized Hermes service to be reachable by the backend.

Common Hermes environment variables:

```bash
CITADEL_HERMES_BASE_URL=http://127.0.0.1:8787
CITADEL_HERMES_PASSWORD=
CITADEL_HERMES_TIMEOUT=600
CITADEL_HERMES_SYNC_TIMEOUT=8
```

Notes:

- `CITADEL_HERMES_BASE_URL` points Citadel at the local Hermes HTTP service.
- `CITADEL_HERMES_PASSWORD` is optional, but should match Hermes if that service requires login.
- `CITADEL_HERMES_TIMEOUT` controls longer chat/agent calls.
- `CITADEL_HERMES_SYNC_TIMEOUT` controls shorter status/session sync calls.
- `HERMES_HOME` can be set when the status dashboard should read Hermes skill usage from a non-default Hermes home. If unset, Citadel also checks `~/.hermes`.

## Install and Run

Citadel still follows the upstream Open WebUI development shape. The extra requirement is that Hermes should be running and reachable before you expect Hermes profiles, automations, and sessions to appear.

### Local development

```bash
cd /home/edgesecure/Citadel
npm install
pip install -e .
export CITADEL_HERMES_BASE_URL=http://127.0.0.1:8787
open-webui serve
```

In another shell, run the frontend dev server when working on Svelte UI changes:

```bash
cd /home/edgesecure/Citadel
npm run dev
```

### Docker-style deployment

Use the upstream Docker guidance below as the base. Add the Hermes variables to the Citadel container or compose service:

```bash
environment:
  CITADEL_HERMES_BASE_URL: http://host.docker.internal:8787
  CITADEL_HERMES_PASSWORD: ${CITADEL_HERMES_PASSWORD}
  CITADEL_HERMES_TIMEOUT: "600"
  CITADEL_HERMES_SYNC_TIMEOUT: "8"
```

If Hermes runs on the same Linux host as Docker, make sure the container can resolve and reach the host address you place in `CITADEL_HERMES_BASE_URL`.

## Operational Notes

- Refresh models after changing Hermes profiles so Citadel can rebuild the `hermes:<profile>` virtual model list.
- Use `/api/v1/hermes/status` or the Status page to confirm Citadel can reach Hermes.
- Use `/api/v1/hermes/sync` when Hermes sessions should be pulled into the Citadel chat list.
- Automations in this fork are expected to come from Hermes cron jobs, not the old standalone Citadel automation storage path.
- If the Status page reports that it received HTML or another non-JSON response, restart the Citadel backend so the `/api/v1/status/summary` route is loaded.

---

## Original Open WebUI README

# Open WebUI 👋

![GitHub stars](https://img.shields.io/github/stars/open-webui/open-webui?style=social)
![GitHub forks](https://img.shields.io/github/forks/open-webui/open-webui?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/open-webui/open-webui?style=social)
![GitHub repo size](https://img.shields.io/github/repo-size/open-webui/open-webui)
![GitHub language count](https://img.shields.io/github/languages/count/open-webui/open-webui)
![GitHub top language](https://img.shields.io/github/languages/top/open-webui/open-webui)
![GitHub last commit](https://img.shields.io/github/last-commit/open-webui/open-webui?color=red)
[![Discord](https://img.shields.io/badge/Discord-Open_WebUI-blue?logo=discord&logoColor=white)](https://discord.gg/5rJgQTnV4s)
[![](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/tjbck)

![Open WebUI Banner](./banner.png)

**Open WebUI is an [extensible](https://docs.openwebui.com/features/extensibility/plugin), feature-rich, and user-friendly self-hosted AI platform designed to operate entirely offline.** It supports various LLM runners like **Ollama** and **OpenAI-compatible APIs**, with **built-in inference engine** for RAG, making it a **powerful AI deployment solution**.

Passionate about open-source AI? [Join our team →](https://careers.openwebui.com/)

![Open WebUI Demo](./demo.png)

> [!TIP]  
> **Looking for an [Enterprise Plan](https://docs.openwebui.com/enterprise)?** – **[Speak with Our Sales Team Today!](https://docs.openwebui.com/enterprise)**
>
> Get **enhanced capabilities**, including **custom theming and branding**, **Service Level Agreement (SLA) support**, **Long-Term Support (LTS) versions**, and **more!**

For more information, be sure to check out our [Open WebUI Documentation](https://docs.openwebui.com/).

## Key Features of Open WebUI ⭐

- 🚀 **Effortless Setup**: Install seamlessly using Docker or Kubernetes (kubectl, kustomize or helm) for a hassle-free experience with support for both `:ollama` and `:cuda` tagged images.

- 🤝 **Ollama/OpenAI API Integration**: Effortlessly integrate OpenAI-compatible APIs for versatile conversations alongside Ollama models. Customize the OpenAI API URL to link with **LMStudio, GroqCloud, Mistral, OpenRouter, and more**.

- 🛡️ **Granular Permissions and User Groups**: By allowing administrators to create detailed user roles and permissions, we ensure a secure user environment. This granularity not only enhances security but also allows for customized user experiences, fostering a sense of ownership and responsibility amongst users.

- 📱 **Responsive Design**: Enjoy a seamless experience across Desktop PC, Laptop, and Mobile devices.

- 📱 **Progressive Web App (PWA) for Mobile**: Enjoy a native app-like experience on your mobile device with our PWA, providing offline access on localhost and a seamless user interface.

- ✒️🔢 **Full Markdown and LaTeX Support**: Elevate your LLM experience with comprehensive Markdown and LaTeX capabilities for enriched interaction.

- 🎤📹 **Hands-Free Voice/Video Call**: Experience seamless communication with integrated hands-free voice and video call features using multiple Speech-to-Text providers (Local Whisper, OpenAI, Deepgram, Azure) and Text-to-Speech engines (Azure, ElevenLabs, OpenAI, Transformers, WebAPI), allowing for dynamic and interactive chat environments.

- 🛠️ **Model Builder**: Easily create Ollama models via the Web UI. Create and add custom characters/agents, customize chat elements, and import models effortlessly through [Open WebUI Community](https://openwebui.com/) integration.

- 🐍 **Native Python Function Calling Tool**: Enhance your LLMs with built-in code editor support in the tools workspace. Bring Your Own Function (BYOF) by simply adding your pure Python functions, enabling seamless integration with LLMs.

- 💾 **Persistent Artifact Storage**: Built-in key-value storage API for artifacts, enabling features like journals, trackers, leaderboards, and collaborative tools with both personal and shared data scopes across sessions.

- 📚 **Local RAG Integration**: Dive into the future of chat interactions with groundbreaking Retrieval Augmented Generation (RAG) support using your choice of 9 vector databases and multiple content extraction engines (Tika, Docling, Document Intelligence, Mistral OCR, PaddleOCR-vl, External loaders). Load documents directly into chat or add files to your document library, effortlessly accessing them using the `#` command before a query.

- 🔍 **Web Search for RAG**: Perform web searches using 15+ providers including `SearXNG`, `Google PSE`, `Brave Search`, `Kagi`, `Mojeek`, `Tavily`, `Perplexity`, `serpstack`, `serper`, `Serply`, `DuckDuckGo`, `SearchApi`, `SerpApi`, `Bing`, `Jina`, `Exa`, `Sougou`, `Azure AI Search`, and `Ollama Cloud`, injecting results directly into your chat experience.

- 🌐 **Web Browsing Capability**: Seamlessly integrate websites into your chat experience using the `#` command followed by a URL. This feature allows you to incorporate web content directly into your conversations, enhancing the richness and depth of your interactions.

- 🎨 **Image Generation & Editing Integration**: Create and edit images using multiple engines including OpenAI's DALL-E, Gemini, ComfyUI (local), and AUTOMATIC1111 (local), with support for both generation and prompt-based editing workflows.

- ⚙️ **Many Models Conversations**: Effortlessly engage with various models simultaneously, harnessing their unique strengths for optimal responses. Enhance your experience by leveraging a diverse set of models in parallel.

- 🔐 **Role-Based Access Control (RBAC)**: Ensure secure access with restricted permissions; only authorized individuals can access your Ollama, and exclusive model creation/pulling rights are reserved for administrators.

- 🗄️ **Flexible Database & Storage Options**: Choose from SQLite (with optional encryption), PostgreSQL, or configure cloud storage backends (S3, Google Cloud Storage, Azure Blob Storage) for scalable deployments.

- 🔍 **Advanced Vector Database Support**: Select from 9 vector database options including ChromaDB, PGVector, Qdrant, Milvus, Elasticsearch, OpenSearch, Pinecone, S3Vector, and Oracle 23ai for optimal RAG performance.

- 🔐 **Enterprise Authentication**: Full support for LDAP/Active Directory integration, SCIM 2.0 automated provisioning, and SSO via trusted headers alongside OAuth providers. Enterprise-grade user and group provisioning through SCIM 2.0 protocol, enabling seamless integration with identity providers like Okta, Azure AD, and Google Workspace for automated user lifecycle management.

- ☁️ **Cloud-Native Integration**: Native support for Google Drive and OneDrive/SharePoint file picking, enabling seamless document import from enterprise cloud storage.

- 📊 **Production Observability**: Built-in OpenTelemetry support for traces, metrics, and logs, enabling comprehensive monitoring with your existing observability stack.

- ⚖️ **Horizontal Scalability**: Redis-backed session management and WebSocket support for multi-worker and multi-node deployments behind load balancers.

- 🌐🌍 **Multilingual Support**: Experience Open WebUI in your preferred language with our internationalization (i18n) support. Join us in expanding our supported languages! We're actively seeking contributors!

- 🧩 **Pipelines, Open WebUI Plugin Support**: Seamlessly integrate custom logic and Python libraries into Open WebUI using [Pipelines Plugin Framework](https://github.com/open-webui/pipelines). Launch your Pipelines instance, set the OpenAI URL to the Pipelines URL, and explore endless possibilities. [Examples](https://github.com/open-webui/pipelines/tree/main/examples) include **Function Calling**, User **Rate Limiting** to control access, **Usage Monitoring** with tools like Langfuse, **Live Translation with LibreTranslate** for multilingual support, **Toxic Message Filtering** and much more.

- 🌟 **Continuous Updates**: We are committed to improving Open WebUI with regular updates, fixes, and new features.

Want to learn more about Open WebUI's features? Check out our [Open WebUI documentation](https://docs.openwebui.com/features) for a comprehensive overview!

---

We are incredibly grateful for the generous support of our sponsors. Their contributions help us to maintain and improve our project, ensuring we can continue to deliver quality work to our community. Thank you!

## How to Install 🚀

### Installation via Python pip 🐍

Open WebUI can be installed using pip, the Python package installer. Before proceeding, ensure you're using **Python 3.11** to avoid compatibility issues.

1. **Install Open WebUI**:
   Open your terminal and run the following command to install Open WebUI:

   ```bash
   pip install open-webui
   ```

2. **Running Open WebUI**:
   After installation, you can start Open WebUI by executing:

   ```bash
   open-webui serve
   ```

This will start the Open WebUI server, which you can access at [http://localhost:8080](http://localhost:8080)

### Quick Start with Docker 🐳

> [!NOTE]  
> Please note that for certain Docker environments, additional configurations might be needed. If you encounter any connection issues, our detailed guide on [Open WebUI Documentation](https://docs.openwebui.com/) is ready to assist you.

> [!WARNING]
> When using Docker to install Open WebUI, make sure to include the `-v open-webui:/app/backend/data` in your Docker command. This step is crucial as it ensures your database is properly mounted and prevents any loss of data.

> [!TIP]  
> If you wish to utilize Open WebUI with Ollama included or CUDA acceleration, we recommend utilizing our official images tagged with either `:cuda` or `:ollama`. To enable CUDA, you must install the [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/) on your Linux/WSL system.

### Installation with Default Configuration

- **If Ollama is on your computer**, use this command:

  ```bash
  docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

- **If Ollama is on a Different Server**, use this command:

  To connect to Ollama on another server, change the `OLLAMA_BASE_URL` to the server's URL:

  ```bash
  docker run -d -p 3000:8080 -e OLLAMA_BASE_URL=https://example.com -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

- **To run Open WebUI with Nvidia GPU support**, use this command:

  ```bash
  docker run -d -p 3000:8080 --gpus all --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:cuda
  ```

### Installation for OpenAI API Usage Only

- **If you're only using OpenAI API**, use this command:

  ```bash
  docker run -d -p 3000:8080 -e OPENAI_API_KEY=your_secret_key -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

### Installing Open WebUI with Bundled Ollama Support

This installation method uses a single container image that bundles Open WebUI with Ollama, allowing for a streamlined setup via a single command. Choose the appropriate command based on your hardware setup:

- **With GPU Support**:
  Utilize GPU resources by running the following command:

  ```bash
  docker run -d -p 3000:8080 --gpus=all -v ollama:/root/.ollama -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:ollama
  ```

- **For CPU Only**:
  If you're not using a GPU, use this command instead:

  ```bash
  docker run -d -p 3000:8080 -v ollama:/root/.ollama -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:ollama
  ```

Both commands facilitate a built-in, hassle-free installation of both Open WebUI and Ollama, ensuring that you can get everything up and running swiftly.

After installation, you can access Open WebUI at [http://localhost:3000](http://localhost:3000). Enjoy! 😄

### Other Installation Methods

We offer various installation alternatives, including non-Docker native installation methods, Docker Compose, Kustomize, and Helm. Visit our [Open WebUI Documentation](https://docs.openwebui.com/getting-started/) or join our [Discord community](https://discord.gg/5rJgQTnV4s) for comprehensive guidance.

### Troubleshooting

Encountering connection issues? Our [Open WebUI Documentation](https://docs.openwebui.com/troubleshooting/) has got you covered. For further assistance and to join our vibrant community, visit the [Open WebUI Discord](https://discord.gg/5rJgQTnV4s).

#### Open WebUI: Server Connection Error

If you're experiencing connection issues, it’s often due to the WebUI docker container not being able to reach the Ollama server at 127.0.0.1:11434 (host.docker.internal:11434) inside the container . Use the `--network=host` flag in your docker command to resolve this. Note that the port changes from 3000 to 8080, resulting in the link: `http://localhost:8080`.

**Example Docker Command**:

```bash
docker run -d --network=host -v open-webui:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name open-webui --restart always ghcr.io/open-webui/open-webui:main
```

### Keeping Your Docker Installation Up-to-Date

Check our Updating Guide available in our [Open WebUI Documentation](https://docs.openwebui.com/getting-started/updating).

### Using the Dev Branch 🌙

> [!WARNING]
> The `:dev` branch contains the latest unstable features and changes. Use it at your own risk as it may have bugs or incomplete features.

If you want to try out the latest bleeding-edge features and are okay with occasional instability, you can use the `:dev` tag like this:

```bash
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name open-webui --add-host=host.docker.internal:host-gateway --restart always ghcr.io/open-webui/open-webui:dev
```

### Offline Mode

If you are running Open WebUI in an offline environment, you can set the `HF_HUB_OFFLINE` environment variable to `1` to prevent attempts to download models from the internet.

```bash
export HF_HUB_OFFLINE=1
```

## What's Next? 🌟

Discover upcoming features on our roadmap in the [Open WebUI Documentation](https://docs.openwebui.com/roadmap/).

## License 📜

This project contains code under multiple licenses. The current codebase includes components licensed under the Open WebUI License with an additional requirement to preserve the "Open WebUI" branding, as well as prior contributions under their respective original licenses. For a detailed record of license changes and the applicable terms for each section of the code, please refer to [LICENSE_HISTORY](./LICENSE_HISTORY). For complete and updated licensing details, please see the [LICENSE](./LICENSE) and [LICENSE_HISTORY](./LICENSE_HISTORY) files.

## Support 💬

If you have any questions, suggestions, or need assistance, please open an issue or join our
[Open WebUI Discord community](https://discord.gg/5rJgQTnV4s) to connect with us! 🤝

## Star History

<a href="https://star-history.com/#open-webui/open-webui&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date" />
  </picture>
</a>

---

Created by [Timothy Jaeryang Baek](https://github.com/tjbck) - Let's make Open WebUI even more amazing together! 💪
