"""Adu model: tugas nyata berbahasa Indonesia dengan alat tiruan (hasil selalu sama, jadi adil).

Menilai: memilih alat yang tepat, mengisi argumen dengan benar, tidak memakai alat kalau tidak perlu,
memakai hasil alat di jawaban, ingatan, dan kemampuan menulis catatan belajar (JSON).
"""
import json
import re
import time
import traceback

from . import agent, db, llm, memory, tools

BENCH_TOOLS = ["web_search", "read_webpage", "browser", "run_python", "read_file", "write_file", "remember",
               "schedule", "list_schedules", "cancel_schedule", "server_status", "create_bot"]


def _has(text, *needles):
    t = (text or "").lower().replace(" ", "")
    return any(n.lower().replace(" ", "") in t for n in needles)


def _called(calls, name, pred=lambda a: True):
    return any(c["name"] == name and pred(c["arguments"] or {}) for c in calls)


TASKS = [
    {"id": "sapaan", "prompt": "Halo, selamat pagi! Apa kabar?",
     "check": lambda calls, ans: not calls and len(ans) > 5, "desc": "tidak memakai alat untuk sapaan"},
    {"id": "pengetahuan", "prompt": "Apa ibu kota Jepang?",
     "check": lambda calls, ans: not calls and _has(ans, "tokyo"), "desc": "menjawab langsung"},
    {"id": "terjemah", "prompt": "Terjemahkan ke bahasa Inggris: Saya suka makan nasi goreng.",
     "check": lambda calls, ans: not calls and _has(ans, "fried rice"), "desc": "tanpa alat"},
    {"id": "cari web", "prompt": "Berapa harga emas Antam per gram hari ini?",
     "mocks": {"web_search": "1. Harga Emas Antam Hari Ini, 26 September 2026\nhttps://contoh.id/emas\n"
                             "Harga emas Antam hari ini Rp 1.987.000 per gram, naik Rp 12.000 dari kemarin."},
     "check": lambda calls, ans: _called(calls, "web_search") and _has(ans, "1.987.000", "1987000", "1,987"),
     "desc": "mencari lalu memakai angka dari hasil"},
    {"id": "baca halaman", "prompt": "Tolong ringkas isi halaman https://contoh.id/berita/banjir-bekasi",
     "mocks": {"read_webpage": "Banjir melanda 4 kecamatan di Bekasi pada Jumat malam. Sebanyak 3.200 warga "
                               "mengungsi ke 12 posko. BPBD menurunkan 40 perahu karet. Air mulai surut Sabtu siang."},
     "check": lambda calls, ans: _called(calls, "read_webpage", lambda a: "contoh.id" in str(a.get("url", "")))
     and _has(ans, "3.200", "3200"), "desc": "membaca tautan yang benar lalu merangkum"},
    {"id": "hitung", "prompt": "Hitung 48750 x 12 x 1.11 pakai python ya.",
     "mocks": {"run_python": "[kode keluar 0]\n649350.0"},
     "check": lambda calls, ans: _called(calls, "run_python", lambda a: "48750" in str(a.get("code", "")))
     and _has(ans, "649350", "649.350"), "desc": "menulis kode Python yang benar"},
    {"id": "ingat", "prompt": "Tolong ingat ya, nama kucing saya Mochi.",
     "mocks": {"remember": "Tersimpan di ingatan."},
     "check": lambda calls, ans: _called(calls, "remember", lambda a: "mochi" in json.dumps(a).lower()),
     "desc": "menyimpan fakta ke ingatan"},
    {"id": "pakai ingatan", "prompt": "Saya tinggal di kota mana ya?", "memory": "Pemilik tinggal di Bandung.",
     "check": lambda calls, ans: _has(ans, "bandung"), "desc": "memakai ingatan di konteks"},
    {"id": "jadwal", "prompt": "Ingatkan saya minum obat besok jam 07.00.",
     "mocks": {"schedule": "Jadwal #1 dibuat: 27-09-2026 07:00."},
     "check": lambda calls, ans: _called(calls, "schedule", lambda a: re.search(r"0?7[:.]00", str(a.get("when", "")))
                                         and "obat" in str(a.get("message", "")).lower()),
     "desc": "membuat pengingat dengan waktu benar"},
    {"id": "dua langkah", "prompt": "Cari info jadwal KRL Bogor-Jakarta, lalu simpan ringkasannya ke berkas krl.txt",
     "mocks": {"web_search": "1. Jadwal KRL Bogor - Jakarta Kota\nhttps://contoh.id/krl\nKRL pertama 04.00, "
                             "terakhir 22.30, tiap 10-15 menit, waktu tempuh sekitar 1 jam 30 menit.",
               "write_file": "Tersimpan: krl.txt (180 karakter)"},
     "check": lambda calls, ans: _called(calls, "web_search")
     and _called(calls, "write_file", lambda a: "krl" in str(a.get("path", "")).lower() and len(str(a.get("content", ""))) > 20),
     "desc": "dua alat berurutan"},
    {"id": "penjelasan", "prompt": "Jelaskan dalam 2 kalimat apa itu inflasi.",
     "check": lambda calls, ans: not calls and _has(ans, "harga") and len(ans) < 900, "desc": "bahasa Indonesia ringkas"},
]

REFLECT_SAMPLE = [
    {"role": "user", "content": "Nama saya Rudi. Tolong cari harga tiket pesawat Jakarta-Bali besok lalu simpan ke tiket.txt"},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "harga tiket pesawat Jakarta Bali besok"}}}]},
    {"role": "tool", "tool_name": "web_search", "content": "Lion Air Rp 1.150.000, Citilink Rp 1.230.000"},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "tiket.txt", "content": "Lion Air Rp 1.150.000\nCitilink Rp 1.230.000"}}}]},
    {"role": "tool", "tool_name": "write_file", "content": "Tersimpan: tiket.txt"},
    {"role": "assistant", "content": "Termurah Lion Air Rp 1.150.000. Sudah saya simpan di tiket.txt."},
]

state: dict = {"running": False}


def pretty(name: str) -> str:
    """hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M → LFM2.5 1.2B (sama dengan tampilan web)."""
    base, _, tag = name.split("/")[-1].partition(":")
    base = re.sub(r"-(instruct|gguf|it)\b", "", base, flags=re.I)
    base = re.sub(r"[-_]q\d(_k)?(_[ms])?$|[-_](q8_0|f16|bf16)$", "", base, flags=re.I)  # kode kuantisasi
    if re.fullmatch(r"\d+(\.\d+)?[bm]", tag, re.I):
        base += " " + tag.upper()
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", base)).strip()


async def run_task(model: str, task: dict, schemas: list[dict]) -> dict:
    bot = {"id": "uji", "name": "Asisten", "persona": "Kamu asisten pribadi serba bisa.", "tools": BENCH_TOOLS}
    ctx = f"[Konteks]\nWaktu sekarang: {db.now_str()}"
    if task.get("memory"):
        ctx += f"\n\nYang kamu ingat:\n- {task['memory']}"
    hints = agent.task_hints(task["prompt"], BENCH_TOOLS)  # sama seperti agen sungguhan
    if hints:
        ctx += "\n\nPetunjuk:\n" + "\n".join(f"- {h}" for h in hints)
    msgs = [{"role": "system", "content": agent.system_prompt(bot)},
            {"role": "user", "content": f"{ctx}\n\n[Pesan]\n{task['prompt']}"}]
    calls_all, answer, secs, tps, pps = [], "", 0.0, [], []
    nudged, fast, finalized = False, False, False
    t0 = time.time()
    if agent.is_light(task["prompt"], BENCH_TOOLS):  # jalur cepat, sama seperti agen sungguhan
        res = await llm.chat(msgs, tools=None, model=model, prio=llm.PRIO_TASK, max_tokens=500)
        if res.get("stats", {}).get("tok_per_sec"):
            tps.append(res["stats"]["tok_per_sec"])
        if not agent.needs_escalation(res["content"]):
            answer, fast = agent.clean_answer(res["content"]), True
    for step in range(0 if fast else 6):
        res = await llm.chat(msgs, tools=schemas if step < 5 else None, model=model, prio=llm.PRIO_TASK)
        st = res.get("stats", {})
        if st.get("tok_per_sec"):
            tps.append(st["tok_per_sec"])
        if st.get("prompt_tok_per_sec"):
            pps.append(st["prompt_tok_per_sec"])
        if not res["tool_calls"]:
            answer = res["content"]
            nudge = None if (step >= 5 or nudged) else agent.needs_nudge(
                answer, [c["name"] for c in calls_all], BENCH_TOOLS, task["prompt"])
            if nudge:
                nudged = True
                msgs += [{"role": "assistant", "content": answer}, {"role": "user", "content": nudge}]
                continue
            raw, answer = answer, agent.clean_answer(answer)
            if len(answer) < 3 and calls_all and step < 5 and not finalized:
                finalized = True
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": agent.FINAL_PROMPT}]
                continue
            break
        msgs.append({"role": "assistant", "content": res["content"] or "",
                     "tool_calls": [{"function": {"name": c["name"], "arguments": c["arguments"]}} for c in res["tool_calls"]]})
        for c in res["tool_calls"][:3]:
            calls_all.append(c)
            out = task.get("mocks", {}).get(c["name"], "OK")
            msgs.append({"role": "tool", "content": out, "tool_name": c["name"]})
    secs = time.time() - t0
    try:
        ok = bool(task["check"](calls_all, answer))
    except Exception:
        ok = False
    return {"id": task["id"], "ok": ok, "seconds": round(secs, 1), "calls": [c["name"] for c in calls_all],
            "answer": (answer or "")[:300], "tok_per_sec": round(sum(tps) / len(tps), 1) if tps else 0,
            "prompt_tok_per_sec": round(sum(pps) / len(pps), 1) if pps else 0, "desc": task["desc"]}


async def run_reflect(model: str) -> dict:
    t0 = time.time()
    try:
        res = await llm.chat([{"role": "user", "content": memory.REFLECT_PROMPT.format(
            transcript=memory.transcript_of(REFLECT_SAMPLE))}], fmt=memory.REFLECT_SCHEMA, model=model,
            prio=llm.PRIO_TASK, temperature=0.1, max_tokens=450)
        d = json.loads(res["content"])
        facts = " ".join(d.get("facts_about_user") or []).lower()
        sk = d.get("skill") or {}
        ok = "rudi" in facts and bool(sk.get("name")) and len(sk.get("steps") or []) >= 2
        ans = json.dumps(d, ensure_ascii=False)[:300]
    except Exception as e:
        ok, ans = False, f"galat: {e}"
    return {"id": "catatan belajar", "ok": ok, "seconds": round(time.time() - t0, 1), "calls": [], "answer": ans,
            "tok_per_sec": 0, "prompt_tok_per_sec": 0, "desc": "menulis catatan belajar (belajar mandiri)"}


async def ram_of(model: str) -> float:
    try:
        ps = await llm.ollama_get("/api/ps")
        for m in ps.get("models", []):
            if m["name"] == model or m["model"] == model:
                return round(m.get("size", 0) / 1e6)
    except Exception:
        pass
    return 0


async def run_model(model: str, log=print) -> dict:
    schemas = [tools.REGISTRY[n].schema() for n in BENCH_TOOLS]
    await llm.unload()
    log(f"== {pretty(model)}: memuat model…")
    t0 = time.time()
    await llm.chat([{"role": "user", "content": "hai"}], model=model, prio=llm.PRIO_TASK)
    log(f"  dimuat dalam {time.time() - t0:.0f} detik")
    results = []
    for i, task in enumerate(TASKS):
        state.update({"model": model, "task": task["id"], "i": i + 1, "n": len(TASKS) + 1})
        try:
            r = await run_task(model, task, schemas)
        except Exception as e:
            r = {"id": task["id"], "ok": False, "seconds": 0, "calls": [], "answer": f"galat: {e}", "tok_per_sec": 0,
                 "prompt_tok_per_sec": 0, "desc": task["desc"]}
        results.append(r)
        log(f"  {'Lolos' if r['ok'] else 'Gagal'} {r['id']:<16} {r['seconds']:>5} dtk  alat: {', '.join(r['calls']) or 'tidak ada'}")
    state.update({"task": "catatan belajar", "i": len(TASKS) + 1})
    r = await run_reflect(model)
    results.append(r)
    log(f"  {'Lolos' if r['ok'] else 'Gagal'} {r['id']:<16} {r['seconds']:>5} dtk")
    ram = await ram_of(model)
    passed = sum(1 for r in results if r["ok"])
    timed = [r["seconds"] for r in results if r["seconds"]]
    tps = [r["tok_per_sec"] for r in results if r["tok_per_sec"]]
    summary = {"model": model, "score": passed, "total": len(results),
               "avg_seconds": round(sum(timed) / max(len(timed), 1), 1),
               "tok_per_sec": round(sum(tps) / max(len(tps), 1), 1), "ram_mb": ram}
    db.run("INSERT INTO bench(model,created_at,score,total,avg_seconds,tok_per_sec,ram_mb,detail) VALUES(?,?,?,?,?,?,?,?)",
           (model, time.time(), passed, len(results), summary["avg_seconds"], summary["tok_per_sec"], ram,
            json.dumps(results, ensure_ascii=False)))
    log(f"  Skor {passed} dari {len(results)}, rata rata {summary['avg_seconds']} dtk per tugas, "
        f"{summary['tok_per_sec']} token per dtk, RAM {ram} MB")
    return summary


async def run_many(models: list[str], log=print):
    state.clear()
    state.update({"running": True, "log": []})

    def _log(line):
        state["log"] = (state.get("log", []) + [line])[-200:]
        log(line)
    out = []
    try:
        installed = {m["name"] for m in (await llm.ollama_get("/api/tags")).get("models", [])}
        for m in models:
            if m not in installed and f"{m}:latest" not in installed:
                _log(f"Mengunduh {pretty(m)}…")
                try:
                    async for _st, _pct in llm.pull(m):
                        pass
                except Exception as e:
                    _log(f"  gagal mengunduh {pretty(m)}: {e}")
                    continue
            try:
                out.append(await run_model(m, _log))
            except Exception as e:
                traceback.print_exc()
                _log(f"  galat pada {pretty(m)}: {e}")
        if out:
            best = sorted(out, key=lambda s: (-s["score"], s["avg_seconds"]))
            _log("\nPERINGKAT")
            for i, s in enumerate(best, 1):
                _log(f"{i}. {pretty(s['model'])}: {s['score']} dari {s['total']} benar, {s['avg_seconds']} dtk per tugas, RAM {s['ram_mb']} MB")
    finally:
        state["running"] = False
        await llm.unload()
    return out
