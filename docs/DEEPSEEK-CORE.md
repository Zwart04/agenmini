# Agen Mini core, adapted from DeepSeek Harness

The built-in Python core adapts the lifecycle and exclusive scheduler contracts
from `deepseek-ai/deepseek-harness` at commit
`5badb15009ae1756c3afe0ae0cef1faafc290ccc` (MIT):
`packages/core/agent-loop/src/agent.ts` and `src/tool-calls.ts`.
It is not the upstream CLI, Cordis runtime, a complete port, or a prompt profile.
The original DeepSeek external runtime remains separately selectable.

Flow: scoped context → model request → validate schema/permission → exclusive
tool execution → durable identified result → next step → verify → final reply.
Web and Telegram both enter `agent.Turn.run`. Streaming text is presentation;
the chat message remains the authoritative answer. The SQLite event journal
records lifecycle/tool outcomes and workspace file changes, not credentials or
raw model requests. Mutations remain ordered. Time and step budgets bound work.

The core is provider-independent: local, direct online API and gateway models
use this same lifecycle. Local small models are evaluation references, not a
restriction on which models can use the harness. Provider-specific sampling
and authentication belong to the model adapter, not the core workflow.
Checks may reject or request repair of a model's source; they must not replace
a failed implementation with an evaluator-authored application template.
Passing a dispatch test proves shared routing, not equivalent model quality.
The guided standalone Python-file path also applies to all three backends:
model-written source → syntax checks → permission → execute assertions →
model repair from actual errors. Print-only claims cannot count as passed tests,
and repairs must preserve existing assertion expressions. This path is enabled
in the assisted profile, not the empty profile. Some local adapter optimizations
(smaller tool menus and sampling) remain model-specific.
An interrupted started call has unknown outcome: inspect its state, never
automatically replay a potentially mutating call. Existing interrupted tasks
still use project checkpoints; this journal does not silently resume them.

The upstream loop has no built-in turn budget; Agen Mini adds its own budget.
Parallel tool pools, Cordis plugin loading, full upstream session projection,
inbox steering and upstream SDK compatibility are not implemented here.
Skills, memory, provider routing and sandbox remain Agen Mini services.
The journal retains at most 2,000 events and 8 MiB of event payload after a turn.
The empty/minimal profile does not enable this adapted core.
No extra Node runtime is needed for this core. RAM improvements must be measured.

## Upstream license

Copyright (c) 2026 DeepSeek. MIT License. Exact upstream notice:
[deepseek-harness.LICENSE](deepseek-harness.LICENSE).
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions: The above copyright notice and this
permission notice shall be included in all copies or substantial portions of
the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
