# Validation - Agen Mini 0.3.4

Checked on 2026-10-02. Testing is separated from deployment and model-quality claims.

## Completed

- Linux pytest suite in the runtime Docker image: 78 passed.
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

Qwen3.5 0.8B was inference-tested; Qwen3.5 2B/4B/9B remain metadata-only checks. Recommendations are conservative RAM/CPU heuristics with an available-memory check, not a leaderboard. Model selection is curated and updated with app releases, not an automatic promise of the newest model globally. Larger models can be much slower on CPU.

Skills/MCP improve available instructions/tools; they do not train weights or guarantee intelligence. Source/number and tool guards reduce specific failure modes; hallucinations remain possible. Actual VPS RAM, disk, provider quotas and throughput remain environment-dependent.


## Additional 0.3.1 checks

- Verified the exact Qwen3.5 0.8B GGUF bytes/hash against the pinned Hugging Face revision and loaded the real file in the pinned llama.cpp container with --no-mmproj. Actual model ID matched /v1/models; process initially observed around 380 MiB before inference. Full agent Python arithmetic returned 1000 in 37.6 seconds. Memory varies with context/use.
- Real pinned FreeLLMAPI image: declarative private account created; login, unified key lookup, provider list and available model list worked. Registered the real local llama.cpp endpoint as a custom upstream and received HTTP 200 with X-Routed-Via custom/qwen35-08b. This tests transport/auth/routing without user provider credentials. The upstream returned a reasoning-style answer under a short token cap; no universal instruction-following claim is made.
- Regression coverage for valid/corrupt/resumable downloads, live health/model-ID matching, duplicate switch rejection, per-bot engine context isolation, seed preservation, and rejecting invented per-bot model IDs. Supervisor mock additionally verifies a stale API request does not stop a DB-selected running local model.
- Four main navigation entries, ten bots, per-bot engine/model editor and native FreeLLMAPI panel were checked in browser. Saved model IDs are validated against connected router/free model lists. Local bots share one active model.
- User VPS logs show successful model loading followed by graceful Exited (0), not a missing-weight exception. The precise external stop trigger is not established from those logs; no remote VPS deployment was performed.

- Real supervisor end-to-end: verified cached Qwen3.5 0.8B was launched through Compose, live health/model alias matched; injecting an obsolete API flag did not change the running local container start time. Switching through the UI to FreeLLMAPI stopped local and started the pinned router; generated private admin credentials worked and live provider/model discovery returned successfully. No provider key from the user was used.
- 0.3.1 desktop/mobile checks include four-menu navigation, ten bots and the persisted per-bot engine/model editor. At 390px, page/modal scroll width equalled viewport width.

- Real download continuation was exercised end-to-end in the packaged app/supervisor with Qwen3.5 0.8B: the UI showed received bytes/percentage, the verified download completed and live readiness changed to Siap. This ran locally in an isolated Docker project, not on the user VPS.

## Additional 0.3.2 checks

- Reproduced the legacy installer replacing a running Bash caller in place: the caller failed while reading fragments of the replacement file. The new installer uses same-directory atomic rename for root scripts and /usr/local/bin/agen. Both the running supervisor and CLI completed their original >100KB script tail after the actual new installer replaced the path; inode changed and stored data/config survived. These use real Bash/file operations and the real installer payload inside a disposable Debian container; system/package/Docker commands are mocked.
- 78 Linux Python tests passed in the 0.3.2 Docker build; 77 Windows tests passed with the Linux sandbox chart test excluded. Supervisor checks, dependency-lock build and JS/Bash syntax passed.
- Browser viewport checks at 320/390/430px: Chat/Workspace/AI/settings, secondary settings tabs, MCP and bot editing; page/form widths had no horizontal overflow. Ten local SVG characters loaded. Bot dialog remained vertically scrollable at 320px; drawer open/outside-close and navigation were exercised. These are browser viewport tests, not a physical iOS/Android keyboard or safe-area certification.
- No commands were executed on the user's VPS in this run. VPS-reported version 0.3.1 after the updater error indicates the earlier payload had already been copied; actual cloud update recovery remains for the user to run.


## Additional 0.3.3 checks

- Linux runtime regression suite: 92 tests passed. JS syntax and Python compilation passed. Installer/supervisor mocks again passed, including the running-script atomic replacement case.
- Real Linux tools: UTF-8 write/read/send roundtrip, isolated Python/shell arithmetic 1000, editing a newly created nested folder as user kerja, remember/recall, schedule/list/cancel (test-only future reminder), live web search and official Python documentation read, and actual stdio MCP hardware invocation.
- Found and fixed a regression guard gap: repeating a failed tool previously produced a synthetic success-like result. The cached original error now remains an error; regression coverage verifies the final task status is failed.
- Real Qwen3.5 0.8B Q4 via pinned llama.cpp (1 CPU thread, context 4096): initial unconstrained full HTML timed out/truncated, and one generic-JSON attempt reached its cap. The final bounded JSON-schema copy + trusted responsive layout produced and attached a complete Seller Studio HTML prototype in 12.2 seconds (2771 bytes). This is a bounded landing-page capability, not proof of reliable general coding by 0.8B.
- Streaming OpenAI-compatible answers/code is exercised against actual local llama.cpp and a protocol test server; native tool arguments are still validated as complete JSON. Timeout errors show an actionable message. All generated HTML/JS/SVG downloads use attachment disposition.
- Public Hugging Face import queried real immutable revisions/LFS hashes; Ollama qwen3:0.6b manifest resolved to one 522640096-byte model layer, and a range fetch returned GGUF magic. Full Ollama-weight inference was not performed. Download corrupt/resume/hash tests cover the shared downloader; additional models are marked untested until actual runtime load.
- Actual pinned 9router and FreeLLMAPI dashboards rendered under owner-authenticated /apps/router/ and /apps/free/. Native navigation between providers/endpoint and models/keys worked. API auth stayed server-side; owner cookie was not forwarded to upstream. No user provider credentials/OAuth exchanges were used.
- Browser: actual animated chat ring, changing CSS transforms on local SVG avatars, queued provider-switch ring, model chooser save, cross-bot history, copying a Telegram fixture into web, and 390px viewport with equal page/client widths were checked. Temporary test data is excluded from releases. Telegram /model callback tests include owner scope/long model IDs; live Telegram network delivery remains untested.

These checks run locally in disposable fixtures, not on the user's VPS. API/provider/email/GitHub/image availability depends on real connections and quotas. Animations are CSS in the browser, with bounded existing SSE queues and paused hidden-tab polling; no animation engine/server render loop or new dependency was added.

## 0.3.4: actual owner VPS validation (2026-10-02)

Earlier sections describe historical fixture runs; this section describes the actual /opt/agenmini VPS.

- Host: Debian 13.6, Linux 6.12.94, 3729 MiB RAM, 2 CPU, 2 GiB swap, approximately 29 GiB free disk. Kernel OOM records exist on September 25–26. The latest pre-repair local shutdown was exit 0 with OOMKilled=false; global DB mode was FreeLLMAPI, so the latest stopped model was not itself proof of an OOM fault.
- Linux regression suite: 93 passed. Installer/supervisor disposable container tests passed: data/config preservation, build failure, atomic replacement of running shell scripts, component setup choices, busy deferral, hardware detection, model selection, release version/checksum rejection. Fresh package installation uses mocks; no empty cloud VPS was provisioned.
- Actual existing-install update completed using the generated installer. Web health passed; code and online SQLite backups were created under data/backup. Secrets, provider state, bots, skills, MCP and conversation data retained. Only required engines started.
- Actual authenticated web/API Seller Studio request before repair: 15.8 seconds, 6143-byte complete HTML downloaded with attachment disposition. After deployment: 5.7 seconds, actual routed model xkiro/mistralai/mistral-medium-3.5 recorded in metadata, generated file attached. This confirms FreeLLMAPI has a working provider in this installation.
- Exact cached Qwen3.5 0.8B SHA256 verified; pinned llama.cpp served health and model ID qwen35-08b with no Ollama daemon. Real local landing-page evaluation: 23.8 seconds; Python 125*8: 26.8 seconds, actual shell output [kode keluar 0] / 1000. Model RSS observed up to roughly 934 MiB, cgroup memory roughly 577 MiB after the trial. Limit calibrated to 1400 MiB plus 700 MiB host reserve; not a universal model benchmark or hallucination-free claim.
- Detected/fixed stale failed status blocking a now-healthy local server, same-model selection failing to request recovery, mandatory idle router startup during updates, standalone CLI using legacy container names, and landing-page metadata hiding the served model behind auto.
- Actual Linux tool roundtrip: nested directory editable by kerja, UTF-8 write/read/list/send, Python and shell, memory save/recall, future test reminder create/list/cancel without delivery, live web search and official Python documentation read, real built-in stdio MCP hardware. Temporary tool tests used separate databases.
- Real consultation orchestrator -> reviewer completed through the configured provider. Its answer included an obsolete Google mobile-test recommendation, illustrating that connected tools/delegation do not guarantee factual advice. No external emails, social posts or trading transactions were performed.
- Authenticated browser: 1280/320/390/430 widths, Chat/Workspace/Koneksi/Pengaturan and subpages; all document scroll widths matched viewport widths, no page JavaScript errors. Real CSS avatar transform changed across frames. Native FreeLLMAPI dashboard returned HTTP 200. Waiting/writing/tool/delegating animation states and hidden-tab pause/polling have regression/code coverage; not every animation was captured live with every provider.
- Real HF/Ollama import inspection returned immutable revisions/model-layer hashes. Cached model full load tested; arbitrary imported model inference and a new complete model download/resume on this VPS were not run. Corrupt/resume/hash paths covered by Linux regression tests. Existing model files retained.
- Existing 9router native API auth/providers/models/combos responded; connected model list was empty. No new provider OAuth login was attempted. Existing dashboard and account data preserved.
- Lightweight fork investigation: 9router-go v1.9.7 binary checksum verified, /health HTTP 200, idle RSS approximately 32 MiB. Docker image digest d3b16a02af319a413f84e7911a7be92e74bda4cde78e5a34f05c35713ae5efba used approximately 12 MiB cgroup idle in an isolated test. Providers/combos JWT endpoints worked; /api/models rejected the current Agen Mini adapter with HTTP 401, including a fresh isolated key setup. It was not substituted for upstream or attached to the owner's router volume. See https://github.com/luqman-v1/9router-go.

Remaining limits: live Telegram delivery/model selection on Telegram requires an owner interaction (regression-tested command/callback paths); real external GitHub/email/image MCP credentials, provider quota exhaustion, OAuth refresh, induced live update rollback, fresh cloud-machine installation, and every arbitrary model architecture are not certified. Web copying Telegram history is regression-tested; no owner Telegram message was sent as a test. Existing provider credentials are never included in source/release assets.
