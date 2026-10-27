# Licensing and third-party notices

Original Agen Mini code, documentation and application artwork starting with
0.11.0: **GNU GPL version 3 or later** (`GPL-3.0-or-later`), copyright (C) 2026
Zwart04. See [LICENSE](LICENSE). Distributed without warranty. Corresponding
source and build scripts are available beside binaries in each GitHub release.

This notice does not relicense third-party components or trademarks, or revoke
permissions already granted under notices in earlier versions.

| Component | Retained terms/source |
| --- | --- |
| DeepSeek loop adaptation | MIT, [original notice](docs/deepseek-harness.LICENSE), [provenance](docs/DEEPSEEK-CORE.md) |
| Connection gateway | MIT, [gateway/LICENSE](gateway/LICENSE), [upstream revision](gateway/UPSTREAM.json) |
| Acorn parser | MIT, [app/vendor/ACORN-LICENSE](app/vendor/ACORN-LICENSE) |
| Provider logos | Upstream artwork/trademarks, [frontend/providers/LICENSE.txt](frontend/providers/LICENSE.txt) |
| Bundled Python | Python Software Foundation and included third-party notices, [python-build-standalone](https://github.com/astral-sh/python-build-standalone) |
| Python distributions | Their installed `.dist-info` license/metadata; versions in `requirements.lock` |
| Node.js / MinGit on Windows | Upstream licenses bundled with the respective distributions; versions/digests in `DEPENDENCIES.json` |

External harnesses are separately installed only when selected. They retain
their own licenses, credentials and terms. API services and providers retain
their names and trademarks; their display does not imply endorsement.
