# Validation â€” Agen Mini 0.3.0

Checked on 2026-10-02. Testing is separated from deployment and model-quality claims.

## Completed

- Linux pytest suite in the runtime Docker image: 69 passed.
- Windows regression suite (Linux sandbox chart test excluded); actual stdio MCP SDK discovery/invocation.
- Installer in a disposable Debian container with package/system commands mocked: fresh Docker install branch, payload extraction, private .env, update preserves data/config, build failure stops instead of reporting success.
- Host supervisor in a disposable container with Docker/network commands mocked: reads real /proc hardware, defers while tasks busy, switches runtime, rejects unknown model IDs, checks versions, rejects bad SHA256.
- Real 9router image: JWT-authenticated providers/models/combos returned HTTP 200; key creation returned 201; authenticated chat passed key validation and correctly rejected missing provider credentials. No provider account was connected.
- Real pinned llama.cpp image loaded QwenPaw Flash 2B Q4, two CPU threads, 4096 context. Process memory observed about 2.04 GiB. Direct arithmetic returned 1000. Full Agen Mini arithmetic executed actual Python and returned 1000 in 33.1 seconds after reducing tool schemas (an earlier run took 73.3 seconds).
- Real-model current-price trial withheld unverified numbers; unknown-email-password question used the deterministic guard. This caught hallucinations seen in the initial run; it does not establish that all answers are factual.
- Real specialist consultation produced a response from Teknisi. Persistent office worker completed a guard task and recorded actual activity logs.
- Office approval integration: file remained absent until authenticated approval, was written afterward, and replay was rejected. Bot-to-bot consultation remains read-only; explicit owner office tasks use target permissions and can request approval.
- Browser desktop/mobile: login, workspace, queued task, completion, logs, hardware/model cards; mobile width 390px had equal client/scroll width, with all character SVGs loaded. UI screenshot artifacts saved separately.
- Final packaged app: health, login, skills, MCP, office, updates and model catalogue endpoints returned HTTP 200.
- JS syntax, Python compilation, Bash syntax, dependency-lock Docker build, self-extracting payload and compose validation.

## Limits

No installation/update was performed on the user's VPS. Installer package installation and rollback/download branch were tested with mocks, not a fresh cloud VM. Automatic release rollback was not induced on a live server. OAuth exchanges, real paid API provider chats, Telegram network delivery, external GitHub/email MCP credentials, and GPU acceleration were not exercised with user accounts. GPU acceleration is not provided by this CPU profile.

Qwen3.5 catalogue files/metadata were checked against Hugging Face; these models have not been inference-tested here. Recommendations are conservative RAM/CPU heuristics with an available-memory check, not a leaderboard. Model selection is curated and updated with app releases, not an automatic promise of the newest model globally. Larger models can be much slower on CPU.

Skills/MCP improve available instructions/tools; they do not train weights or guarantee intelligence. Source/number and tool guards reduce specific failure modes; hallucinations remain possible. Actual VPS RAM, disk, provider quotas and throughput remain environment-dependent.
