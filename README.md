<p align="center">
  <img src="frontend/mascot.png" width="88" alt="Agen Mini mascot">
</p>
<h1 align="center">Agen Mini</h1>
<p align="center"><strong>Your models. Your workspace. Work you can inspect.</strong></p>
<p align="center">A lightweight, self-hosted AI workspace for local models and online providers.<br>Chat, write code, delegate to agents, and inspect every file and tool result behind an answer.</p>
<p align="center">
  <a href="https://github.com/Zwart04/agenmini/releases/latest">Download</a> ·
  <a href="docs/INSTALL.md">Install guide</a> ·
  <a href="docs/BENCHMARKS.md">Benchmark</a> ·
  <a href="README.id.md">Bahasa Indonesia</a>
</p>
<p align="center">
  <a href="https://github.com/Zwart04/agenmini/actions/workflows/test.yml"><img alt="Core tests" src="https://github.com/Zwart04/agenmini/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://github.com/Zwart04/agenmini/actions/workflows/windows.yml"><img alt="Windows installer" src="https://github.com/Zwart04/agenmini/actions/workflows/windows.yml/badge.svg"></a>
  <a href="https://github.com/Zwart04/agenmini/actions/workflows/linux.yml"><img alt="Linux packages" src="https://github.com/Zwart04/agenmini/actions/workflows/linux.yml/badge.svg"></a>
  <a href="https://github.com/Zwart04/agenmini/actions/workflows/harnesses.yml"><img alt="Harness runtimes" src="https://github.com/Zwart04/agenmini/actions/workflows/harnesses.yml/badge.svg"></a>
  <a href="https://github.com/Zwart04/agenmini/actions/workflows/secrets.yml"><img alt="Secret scan" src="https://github.com/Zwart04/agenmini/actions/workflows/secrets.yml/badge.svg"></a>
</p>
<p align="center">
  <img alt="Public preview" src="docs/assets/preview.svg" width="138" height="24">
  <a href="LICENSE"><img alt="License: GPL-3.0-or-later" src="docs/assets/license.svg" width="138" height="24"></a>
</p>

> **Public preview.** Packages and checksums are on [GitHub Releases](https://github.com/Zwart04/agenmini/releases/latest). Provider quotas and local-model availability vary, so expect rough edges.

## What you get

- **Bring your own model.** Use a local OpenAI-compatible endpoint, a direct API key, or the built-in OAuth/API connection gateway. Pick a model per chat or per bot.
- **See the work.** Read the code, diffs, tool log, and source files beside the conversation. Saving checks for conflicts so an agent cannot silently overwrite your edits.
- **One loop everywhere.** Web and Telegram share the same agent loop, with bounded steps, context compaction, and recorded tool results.
- **A small team when needed.** An Orchestrator can delegate to optional specialist bots, each with its own model and tools.
- **Learn without retraining.** Skills, memory, and reviewed procedures are editable files. Agen Mini does not tune model weights.
- **Lean by design.** Native browser UI, system fonts, no Electron shell, no model weights in the package.

## Quick start

1. Download the package for your OS from [Releases](https://github.com/Zwart04/agenmini/releases/latest) and verify its SHA256.
2. Open Agen Mini and choose **Local AI** or **Online AI** first. Optional harness, bot, password, and swap settings live under **Advanced**.
3. Connect a running local model, an online provider, or a direct `/v1` endpoint. Setup finishes only after a real response check succeeds.
4. Pick a model and give the Orchestrator a task. Review tool results and files before accepting the output.

Change the AI source later in **Settings → AI connections & model** (**Pengaturan → Koneksi AI & model**). CLI users on Linux can run `agenmini provider online` then `agenmini model MODEL-ID`; Windows uses `agenmini.cmd`.

## A small model built a working video editor

**Clip Mini** is the documented local-model benchmark: a browser video editor with a CapCut-inspired workflow. It imports a clip, plays and seeks, trims a range, adds text, and exports a downloadable WebM with audio.

[![Clip Mini: actual local-model benchmark with imported video, trim controls, text overlay, and timeline](docs/screenshots/model-editor-v208.png)](docs/BENCHMARKS.md)

| What was tested | Recorded result |
| --- | --- |
| Local models | Qwen3.5 **0.8B** + DeepSeek Coder **1.3B** |
| Browser workflow | Import → playback / seek → trim → text → export → download |
| Export check | WebM decoded; motion, audio, text, and trim verified |
| Example trim | 5-second input → seconds 1–3 → **1.956-second** output with text |
| Recovery | Invalid trim, keyboard input, cancel, and export after cancel |

The harness split work into small parts, checked behavior, and requested repairs. Runtime code came from local-model outputs; contracts, tests, and assembly came from the evaluator. **This was a combined result across multiple attempts, not a one-shot 1B generation.** The editor handles one clip; it is not the full CapCut feature set.

[Read the benchmark, measurements, and provenance →](docs/BENCHMARKS.md)

## A workspace you can follow

[![Agen Mini chat and code panel, captured at 2x resolution with documentation demo data](docs/screenshots/workbench-desktop.png)](docs/screenshots/workbench-desktop.png)

Read code, review changes, and inspect tool activity without leaving the conversation. Preview runs in an isolated frame; backend projects and sites that refuse embedding need their own server or tab.

[Light theme](docs/screenshots/workbench-light.png) · [Editor close-up](docs/screenshots/editor-detail.png) · [Desktop and mobile gallery](docs/screenshots/README.md)

<details>
<summary>Team workspace, provider catalog, and mobile views</summary>

[![Team workspace](docs/screenshots/workspace-desktop.png)](docs/screenshots/workspace-desktop.png)

[![Integrated provider catalog](docs/screenshots/providers-desktop.png)](docs/screenshots/providers-desktop.png)

<p>
  <a href="docs/screenshots/chat-mobile.png"><img src="docs/screenshots/chat-mobile.png" width="280" alt="Chat on mobile"></a>
  <a href="docs/screenshots/workbench-mobile.png"><img src="docs/screenshots/workbench-mobile.png" width="280" alt="Code panel on mobile"></a>
</p>

[Interface tour: MP4, 1920 × 1280](https://raw.githubusercontent.com/Zwart04/agenmini/main/docs/screenshots/preview.mp4) · [Animated GIF](docs/screenshots/preview.gif)

These workspace images use documentation demo data. The model-generated benchmark image and measurements are documented separately.

</details>

## Download

**[Latest release files and checksums →](https://github.com/Zwart04/agenmini/releases/latest)**

| Platform | Package | Includes |
| --- | --- | --- |
| Windows 10 / 11 x64 | `.exe` installer or portable `.zip` | App + `agenmini.cmd` CLI |
| Debian / Ubuntu / Mint | `.deb`, amd64 / arm64 | App + `agenmini` CLI |
| Fedora | `.rpm`, x86_64 / aarch64 | App + CLI |
| Arch / EndeavourOS / Manjaro | `.pkg.tar.zst`, x86_64 | App + CLI |
| Other GNU/Linux | `.tar.gz`, amd64 / arm64, glibc 2.35+ | Bundled Python + gateway |
| macOS / other | Source ZIP, manual setup | No native installer yet |

Linux packages bundle Python and the Go connection gateway. **Node.js, Git, and xdg-utils are system dependencies**; portable installs need them too. The desktop app opens in your existing browser. Packages contain no model weights and no provider accounts.

[Install, update, and uninstall guide](docs/INSTALL.md) · [All releases](https://github.com/Zwart04/agenmini/releases) · [VPS guide](CARA-PASANG-VPS.txt)

## How the harness works

**Load relevant context → choose an action → validate tools and permissions → execute → record results → verify → answer.**

The built-in loop adapts selected control contracts from [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness), with attribution retained. Long chats use context compaction while original messages stay stored. Interrupted mutations are not replayed automatically. External harness runtimes are separate, optional installs with their own permissions and credentials.

[Harness architecture](docs/DEEPSEEK-CORE.md) · [External runtimes](docs/HARNESSES.md) · [Context compaction](docs/CONTEXT-COMPACTION.md)

## Verification

[Core tests](https://github.com/Zwart04/agenmini/actions/workflows/test.yml) · [Windows install](https://github.com/Zwart04/agenmini/actions/workflows/windows.yml) · [Linux packages](https://github.com/Zwart04/agenmini/actions/workflows/linux.yml) · [Runtime matrix](https://github.com/Zwart04/agenmini/actions/workflows/harnesses.yml) · [Secret scan](https://github.com/Zwart04/agenmini/actions/workflows/secrets.yml)

CI covers the core, package installation, login, CLI settings, update/data preservation, and removal. It does not prove every external provider account works or that every generated application is correct. Real-model evaluations are reported separately.

```sh
python -m pytest tests -q
# Optional real local-model evaluation; requires your own llama.cpp and GGUF:
python scripts/evaluate_apps.py --server-exe /path/llama-server --gguf /path/model.gguf
```

[Validation notes](VALIDATION.md) · [Project map](docs/PROJECT-MAP.md) · [Security audit](docs/SECURITY-AUDIT.md) · [Report an issue](https://github.com/Zwart04/agenmini/issues)

## Support development

If Agen Mini helps your work, you can buy its independent developer a coffee. Contributions support maintenance and testing; the app works without a donation. The button opens the developer's **Tako** page.

<a href="https://tako.id/Zwart04/gift"><img src="docs/assets/coffee.svg" width="196" height="48" alt="Buy me a coffee — support Zwart04 on Tako"></a>

## License

Original Agen Mini work from 0.11.0 is **GPL-3.0-or-later**, copyright © 2026 Zwart04. Distributed without warranty. [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md). Dependencies and provider trademarks retain their own terms. Corresponding source and build scripts accompany each binary release.
