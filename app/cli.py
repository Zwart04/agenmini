"""Perintah terminal di dalam container (dipanggil oleh skrip 'agen' di VPS)."""
import asyncio
import json
import secrets
import sys

from . import bench, db, llm, main, web

KANDIDAT = [
    "hf.co/agentscope-ai/QwenPaw-Flash-2B-Q4_K_M",
    "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M",
    "qwen3:1.7b",
    "qwen3.5:0.8b",
    "LiquidAI/lfm2.5-2.6b:q4_k_m",
    "granite4.1:3b",
    "granite4.2:3b",
    "qwen3.5:2b",
]


async def _pull(name):
    last = ""
    async for st, pct in llm.pull(name):
        line = f"{st} {pct}%" if pct is not None else st
        if line != last:
            print(f"\r{line[:70]:<70}", end="", flush=True)
            last = line
    print(f"\n{name} siap.")


async def _bench(models):
    if not models:
        tags = await llm.ollama_get("/api/tags")
        installed = [m["name"] for m in tags.get("models", [])]
        models = [m for m in KANDIDAT if m in installed] + [m for m in KANDIDAT[:3] if m not in installed]
        models = list(dict.fromkeys(models))
    print("Model yang diadu:\n  " + "\n  ".join(models))
    print(f"Perkiraan: 5-15 menit per model di CPU 2 core.\n")
    try:
        res = await bench.run_many(models)
        if res:
            best = sorted(res, key=lambda s: (-s["score"], s["avg_seconds"]))[0]
            print(f"\nSaran: pakai {bench.pretty(best['model'])}. Perintahnya: agen model \"{best['model']}\"")
    finally:
        await llm.session().close()


async def _status():
    s = await web.system_stats()
    print(json.dumps(s, ensure_ascii=False, indent=2))


def usage():
    print(__doc__)


def run():
    main.bootstrap()
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    if cmd == "pull":
        asyncio.run(_pull(args[1]))
    elif cmd == "bench":
        asyncio.run(_bench(args[1:]))
    elif cmd == "model":
        if len(args) < 2:
            print(f"Model sekarang: {db.setting('model')}")
        else:
            db.set_setting("model", args[1])
            print(f"Model diganti ke {args[1]}. Berlaku untuk pesan berikutnya.")
    elif cmd == "password":
        pw = args[1] if len(args) > 1 else secrets.token_urlsafe(9)
        db.set_setting("web_password_hash", web.hash_pw(pw))
        db.set_setting("session_ver", str(int(db.setting("session_ver") or "1") + 1))
        print(f"Kata sandi web baru: {pw}")
    elif cmd == "code":
        print(f"Kode pasangan Telegram: {db.setting('pair_code')}  (kirim ke bot: /kode {db.setting('pair_code')})")
    elif cmd == "telegram":
        db.set_setting("telegram_token", args[1] if len(args) > 1 else "")
        print("Token Telegram disimpan. Mulai ulang agen: agen restart")
    elif cmd == "allow":
        ids = set(json.loads(db.setting("tg_user_ids") or "[]"))
        new = [x for x in args[1:] if x.isdigit()]
        if not new:
            print("User ID diizinkan: " + (", ".join(sorted(ids)) or "belum ada") +
                  "\nTambah: agen izinkan <user id dari @userinfobot>")
        else:
            db.set_setting("tg_user_ids", json.dumps(sorted(ids | set(new))))
            print("Diizinkan: " + ", ".join(new))
    elif cmd == "status":
        asyncio.run(_status())
    elif cmd == "candidates":
        print("\n".join(KANDIDAT))
    else:
        print("perintah: pull <model> | bench [model...] | model [nama] | password [baru] | code | telegram <token> | status")


if __name__ == "__main__":
    run()
