# Agen Mini Gateway

Connection-only fork of 9router-go, itself based on decolua/9router. The exact source revision is in `UPSTREAM.json`; upstream MIT notices are retained in `LICENSE`.

The public application UI belongs to Agen Mini. This binary provides provider credentials, OAuth/refresh, model discovery, fallback combos and LLM streaming. It has no embedded dashboard, media generation, terminal, analytics routes, relay deployment or independent updater. OAuth provider implementations retain their original contracts.

Build: `go build -trimpath -ldflags="-s -w" -o agenmini-gateway ./cmd/agenmini-gateway` (Go 1.27). Run with an isolated `DATA_DIR`, `JWT_SECRET`, `INITIAL_PASSWORD`, `HOST` and `PORT`. Never reuse another running router's data directory. Existing managed data is backed up before changing the runtime.

Native provider logos and the safe display catalog are included in Agen Mini. Trademark ownership remains with each provider. Displayed provider support is not proof of a successful account login or available quota.

Run `python ../tests/check_gateway.py ./agenmini-gateway` to verify the real connection surface with disposable credentials. No paid provider call is made by that check.
