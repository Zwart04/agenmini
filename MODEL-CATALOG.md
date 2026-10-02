# Local model catalogue

Metadata checked against Hugging Face API on 2026-10-02. CPU Q4_K_M, 4096 context. These are curated candidates; no claim that one is the newest or smartest model across all tasks.

| Model | Download | Minimum host RAM | Source |
|---|---:|---:|---|
| QwenPaw Flash 2B | about 1.3 GB | 4 GB | https://huggingface.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M |
| Qwen3.5 0.8B | 579615840 bytes | 3 GB | https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF |
| Qwen3.5 2B | 1396198496 bytes | 5 GB | https://huggingface.co/bartowski/Qwen_Qwen3.5-2B-GGUF |
| Qwen3.5 4B | 3013027808 bytes | 8 GB | https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF |
| Qwen3.5 9B | 6169341984 bytes | 16 GB | https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF |

The Qwen3.5 GGUF repositories were last modified 2026-05-19 in the checked metadata. Original model sources: https://huggingface.co/Qwen/Qwen3.5-2B and https://huggingface.co/Qwen/Qwen3.5-4B . Conversion and original model licenses remain with their authors.

Recommendation uses total RAM, available RAM plus reclaimable local-model memory, and CPU count. It reserves memory for OS/app; the host supervisor rechecks actual available RAM before loading. More parameters is only a capacity heuristic. CPU throughput, other services, GGUF architecture support and real task quality must still be checked.

QwenPaw 2B was actually loaded in the pinned llama.cpp image and evaluated through Agen Mini. Arithmetic with Python succeeded in 33.1 seconds after reducing irrelevant tool schemas, current unsupported price was withheld, and unknown-password question was answered by a deterministic guard. This is a small smoke test, not a comprehensive model benchmark. Larger catalogue models were checked for actual file existence/size but have not been run here.
