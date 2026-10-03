import contextvars
"""Penghubung ke otak: Ollama lokal (utama) dan API online (opsional).

Model kecil sering tidak rapi saat memanggil alat. Karena itu:
- kalau model mendukung alat bawaan Ollama, dipakai;
- kalau tidak, daftar alat ditulis di prompt dan jawabannya diurai sendiri (extract_tool_calls),
  yang mengenali format JSON, <tool_call>, gaya Python [f(x=1)] (LFM), dan XML <function=...> (Qwen).
"""
import ast
import asyncio
import heapq
import json
import re
import time

import aiohttp

from . import db

# ---------- antrean: satu otak, bergiliran. Permintaan pengguna didahulukan dari kerja latar. ----------

PRIO_USER, PRIO_TASK, PRIO_BACKGROUND = 0, 1, 5


class Gate:
    def __init__(self):
        self.busy = False
        self._q: list = []
        self._n = 0
        self.current = ""

    def waiting(self) -> int:
        return sum(1 for *_, f in self._q if not f.done())

    async def acquire(self, prio: int):
        if not self.busy and not self._q:
            self.busy = True
            return
        fut = asyncio.get_running_loop().create_future()
        self._n += 1
        heapq.heappush(self._q, (prio, self._n, fut))
        try:
            await fut
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                self.release()
            raise

    def release(self):
        while self._q:
            _, _, fut = heapq.heappop(self._q)
            if not fut.done():
                fut.set_result(None)
                return
        self.busy = False


gate = Gate()

# ---------- CPU ----------
# Model lokal memakai semua inti CPU saat menulis jawaban (itu sifat semua mesin AI lokal).
# "Hemat CPU" menyisakan satu inti untuk sistem. Jumlah thread sengaja SAMA untuk semua panggilan:
# kalau berbeda, Ollama memuat ulang model tiap kali. Kerja latar diringankan dengan menunggu (wait_idle).
activity = {"last_user": 0.0}


def threads_for(prio: int) -> int | None:
    import os
    if db.setting("cpu_hemat") == "1":
        return max(1, (os.cpu_count() or 2) - 1)
    return None  # biarkan Ollama memakai semua inti (paling cepat)


async def wait_idle(quiet_seconds: int = 90, max_wait: int = 3600) -> bool:
    """Tunggu sampai pemilik berhenti chat sebentar dan otak sedang tidak dipakai."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if not gate.busy and time.time() - activity["last_user"] >= quiet_seconds:
            return True
        await asyncio.sleep(10)
    return False

# Model yang ketahuan tidak mendukung alat bawaan / mode berpikir (diingat supaya tidak dicoba ulang).
_no_native_tools: set[str] = set()
_no_think_param: set[str] = set()

_session: aiohttp.ClientSession | None = None


def session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = None
        if db.setting("dns_aman") != "0":
            from .net import SafeResolver
            connector = aiohttp.TCPConnector(resolver=SafeResolver(), ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=600), connector=connector)
    return _session


class LLMError(Exception):
    pass


def online_ready() -> bool:
    return bool(db.setting("online_base") and db.setting("online_key") and db.setting("online_model"))


# ---------- pengurai panggilan alat dari teks ----------

def _find_json_objects(text: str):
    """Cari objek JSON seimbang {...} di dalam teks."""
    i = 0
    while True:
        start = text.find("{", i)
        if start < 0:
            return
        depth, instr, esc = 0, False, False
        for j in range(start, len(text)):
            ch = text[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            elif ch == '"':
                instr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield start, j + 1, text[start:j + 1]
                    break
        i = start + 1



def _replace_unquoted(s,pattern,replacement):
    parts=[];last=scan=0;quoted=escaped=False
    for match in pattern.finditer(s):
        while scan<match.start():
            char=s[scan];scan+=1
            if escaped:escaped=False
            elif quoted and char=='\\':escaped=True
            elif char=='"':quoted=not quoted
        if quoted:continue
        parts.extend((s[last:match.start()],replacement(match)))
        last=match.end()
    parts.append(s[last:])
    return ''.join(parts)


def _repair_json(s: str):
    """Perbaikan umum untuk JSON berantakan dari model kecil (ide dari mohsinkaleem/agent-mini)."""
    s = re.sub(r"^```(?:json)?\s*", "", s.strip())
    s = re.sub(r"\s*```$", "", s).strip()
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    s = _replace_unquoted(s,re.compile(r"(?<=[{,\s])([A-Za-z_]\w*)\s*:"),lambda m:json.dumps(m[1])+':')
    # Some free gateways return bare simple string values. Repair only complete,
    # unambiguous tokens; truncated strings and complex expressions remain invalid.
    s = _replace_unquoted(s,re.compile(r'(:\s*)([A-Za-z_][A-Za-z0-9_./-]*)(?=\s*[,}])'),
        lambda m:m[1]+(m[2] if m[2] in ('true','false','null') else json.dumps(m[2])))
    return json.loads(s)


def _loads(s: str):
    for fn in (json.loads, _repair_json,
               lambda x: ast.literal_eval(x.replace("true", "True").replace("false", "False").replace("null", "None"))):
        try:
            return fn(s)
        except Exception:
            pass
    return None


def _norm_call(obj, names: set[str]):
    if not isinstance(obj, dict):
        return None
    if "function" in obj and isinstance(obj["function"], dict):
        obj = obj["function"]
    name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
    if isinstance(name,str) and name.startswith(('default.','functions.')) and name.split('.',1)[1] in names:
        name=name.split('.',1)[1]
    if not isinstance(name, str) or name not in names:
        return None
    args = obj.get("arguments", obj.get("args", obj.get("parameters", obj.get("input", {}))))
    if isinstance(args, str):
        args = _loads(args) if args.strip().startswith("{") else {"input": args}
    return {"name": name, "arguments": args if isinstance(args, dict) else None}


def _pythonic_calls(src: str, names: set[str]):
    src = src.strip()
    if not src.startswith("["):
        src = f"[{src}]"
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return []
    out = []
    elts = tree.body.elts if isinstance(tree.body, (ast.List, ast.Tuple)) else [tree.body]
    for node in elts:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
            args = {}
            for kw in node.keywords:
                try:
                    args[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    args[kw.arg] = ast.unparse(kw.value)
            out.append({"name": node.func.id, "arguments": args})
    return out


def extract_tool_calls(text: str, names: set[str]) -> tuple[list[dict], str]:
    """Kembalikan (daftar panggilan, teks sisa)."""
    if not text or not names:
        return [], text
    calls: list[dict] = []
    rest = text

    # 1) Gaya LFM: <|tool_call_start|>[f(a=1)]<|tool_call_end|>
    for m in re.finditer(r"<\|tool_call_start\|>(.*?)(?:<\|tool_call_end\|>|$)", text, re.S):
        calls += _pythonic_calls(m.group(1), names)
    if calls:
        return calls, re.sub(r"<\|tool_call_start\|>.*?(?:<\|tool_call_end\|>|$)", "", text, flags=re.S).strip()

    # 2) Tag <tool>, <tool_call>, <function_call>
    tag_re = r"<(tool_call|tool|function_call|tools)>(.*?)(?:</\1>|$)"
    for m in re.finditer(tag_re, text, re.S):
        body = m.group(2).strip()
        # XML gaya Qwen-coder: <function=nama><parameter=x>nilai</parameter></function>
        fm = re.search(r"<function=([\w\-]+)>(.*?)(?:</function>|$)", body, re.S)
        if fm and fm.group(1) in names:
            args = {k: v.strip() for k, v in re.findall(r"<parameter=([\w\-]+)>(.*?)</parameter>", fm.group(2), re.S)}
            calls.append({"name": fm.group(1), "arguments": args})
            continue
        found = False
        for _, _, js in _find_json_objects(body):
            c = _norm_call(_loads(js), names)
            if c:
                calls.append(c)
                found = True
        if not found:
            calls += _pythonic_calls(body, names)
    if calls:
        return calls, re.sub(tag_re, "", text, flags=re.S).strip()

    # 3) XML tanpa pembungkus
    for m in re.finditer(r"<function=([\w\-]+)>(.*?)(?:</function>|$)", text, re.S):
        if m.group(1) in names:
            args = {k: v.strip() for k, v in re.findall(r"<parameter=([\w\-]+)>(.*?)</parameter>", m.group(2), re.S)}
            calls.append({"name": m.group(1), "arguments": args})
    if calls:
        return calls, re.sub(r"<function=.*?(?:</function>|$)", "", text, flags=re.S).strip()

    # 4) JSON polos {"name": ..., "arguments": ...}
    spans = []
    for s, e, js in _find_json_objects(text):
        if spans and s < spans[-1][1]:
            continue
        c = _norm_call(_loads(js), names)
        if c:
            calls.append(c)
            spans.append((s, e))
    if calls:
        for s, e in reversed(spans):
            rest = rest[:s] + rest[e:]
        rest = re.sub(r"```(?:json)?\s*```", "", rest).strip()
        return calls, rest

    # 5) Panggilan gaya Python di awal jawaban: [web_search(query="x")] atau web_search(query="x")
    stripped = text.strip()
    m = re.match(r"^\[?\s*(\w+)\s*\(", stripped)
    if m and m.group(1) in names:
        end = stripped.find(")]") + 2 if stripped.startswith("[") else len(stripped)
        pc = _pythonic_calls(stripped[:end] if end > 1 else stripped, names)
        if pc:
            return pc, ""
    return [], text


def strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "<think>" in text:  # tidak ditutup
        text = text.split("<think>")[0]
    return text.strip()


# ---------- mode alat lewat teks ----------

def tools_as_text(tools: list[dict]) -> str:
    lines = [
        "\n\n# Tools",
        "You can call tools. To call one, reply with ONLY this (no other text):",
        '<tool>{"name": "TOOL_NAME", "arguments": {"param": "value"}}</tool>',
        "You will then receive the tool result. When you have enough information, answer normally (no <tool> tag).",
        "Never add output/result fields. Tool arguments must contain only the named parameters. For run_python, use print(...) so the tool returns evidence.",
        "Available tools:",
    ]
    for t in tools:
        f = t["function"]
        props = f.get("parameters", {}).get("properties", {})
        req = set(f.get("parameters", {}).get("required", []))
        params = ", ".join(f"{k}{'' if k in req else '?'}: {v.get('type', 'string')}" for k, v in props.items())
        lines.append(f"- {f['name']}({params}): {f['description']}")
    return "\n".join(lines)


def to_text_mode(messages: list[dict], tools: list[dict] | None) -> list[dict]:
    out = []
    for m in messages:
        m = dict(m)
        if m["role"] == "system" and tools:
            m["content"] = m["content"] + tools_as_text(tools)
            tools = None
        elif m["role"] == "assistant" and m.get("tool_calls"):
            calls = "\n".join('<tool>' + json.dumps({"name": c["function"]["name"], "arguments": c["function"]["arguments"]},
                                                    ensure_ascii=False) + '</tool>' for c in m.pop("tool_calls"))
            m["content"] = ((m.get("content") or "") + "\n" + calls).strip()
        elif m["role"] == "tool":
            m = {"role": "user", "content": f"[Tool result: {m.get('tool_name', 'tool')}]\n{m['content']}"}
        out.append(m)
    return out


# ---------- panggilan utama ----------

backend_context = contextvars.ContextVar('bot_backend', default='')

def active_backend():
    return backend_context.get() or db.setting('llm_backend')

def default_model(backend=None):
    backend = backend or active_backend()
    return {'router': db.setting('router_last_model') or (db.setting('model') if db.setting('llm_backend')=='router' and not db.setting('model').startswith(('auto:', 'smart')) else ''),
            'auto':'smart',
            'freellmapi': db.setting('freellmapi_model') or 'auto:smart',
            'local': db.setting('local_model_id') or 'qwenpaw-2b',
            'online': db.setting('online_model')}.get(backend, db.setting('model'))


def normalize_tool_calls(calls, schemas):
    declarations={t['function']['name']:t['function'].get('parameters',{}).get('properties',{}) for t in (schemas or [])}
    aliases={'path':('file_path','filepath','filename'), 'folder':('directory','dir')}
    result=[]
    for call in calls:
        call=dict(call);name=call.get('name','')
        if name.startswith(('default.','functions.')) and name.split('.',1)[1] in declarations:
            name=name.split('.',1)[1];call['name']=name
        args=call.get('arguments')
        if name in declarations and isinstance(args,dict):
            args=dict(args)
            for field,alternatives in aliases.items():
                present=[alias for alias in alternatives if alias in args]
                if field in declarations[name] and field not in args and len(present)==1:
                    args[field]=args.pop(present[0])
            call['arguments']=args
        result.append(call)
    return result


async def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
               on_token=None, prio: int = PRIO_USER, fmt=None, temperature: float = 0.3,
               num_ctx: int | None = None, max_tokens: int | None = None) -> dict:
    """Kembalikan {content, tool_calls, stats}. tool_calls = [{name, arguments}]."""
    if active_backend()=='auto':
        from . import auto_router,office
        routes=await auto_router.candidates(messages);errors=[];emitted=False
        async def token(content):
            nonlocal emitted
            emitted=True
            if on_token:await on_token(content)
        for route in routes:
            office.phase('Router: '+route['backend']+' / '+route['model'],'thinking')
            backend_token=backend_context.set(route['backend'])
            try:
                result=await chat(messages,tools,route['model'],token if on_token else None,prio,fmt,temperature,num_ctx,max_tokens)
                result.setdefault('stats',{})['routing']={'backend':route['backend'],'selected_model':route['model'],'reason':route['reason'],'attempts':len(errors)+1}
                return result
            except (LLMError,ValueError,aiohttp.ClientError,TimeoutError) as exc:
                auto_router.failed(route);errors.append(route['backend']+': '+str(exc)[:180])
                if emitted:raise
            finally:backend_context.reset(backend_token)
        raise LLMError('Semua kandidat router gagal: '+' | '.join(errors))
    model = model or default_model()
    names = {t["function"]["name"] for t in (tools or [])}
    if prio == PRIO_USER:
        activity["last_user"] = time.time()
    from . import office
    if gate.busy: office.phase('Menunggu giliran model…', 'queued')
    await gate.acquire(prio)
    office.phase('Berpikir…', 'thinking')
    gate.current = model
    from . import config
    busy_path = config.DATA_DIR / "model-busy"
    try:
        busy_path.parent.mkdir(parents=True, exist_ok=True)
        busy_path.write_text(model or "AI")
        if model == "online" or active_backend() == "online":
            res = await _chat_online(messages, tools, temperature, fmt, model_override=model if model != "online" else None, max_tokens=max_tokens, on_token=on_token)
        elif active_backend() in ("compatible", "router", "local", "freellmapi"):
            if active_backend() == "router" or (active_backend() == "compatible" and db.setting("compatible_base").rstrip("/") == "http://router:20128/v1"):
                from . import router
                await router.ensure_key()
            res = await _chat_online(messages, tools, temperature, fmt, local=True, model_override=model, max_tokens=max_tokens, on_token=on_token)
        else:
            res = await _chat_ollama(messages, tools, model, on_token, fmt, temperature, num_ctx, max_tokens,
                                     threads_for(prio))
    except Exception:
        from . import usage_meter
        usage_meter.record(active_backend(),model,{})
        raise
    finally:
        busy_path.unlink(missing_ok=True)
        gate.current = ""
        gate.release()

    content = strip_think(res.get("content", ""))
    calls = res.get("tool_calls") or []
    if not calls and names:
        calls, content = extract_tool_calls(content, names)
    res["content"] = content
    res["tool_calls"] = normalize_tool_calls(calls, tools)
    from . import usage_meter
    cost=usage_meter.record(active_backend(),model,res.get("stats",{}))
    res.setdefault("stats",{})["cost_usd"]=cost
    if any(not isinstance(c.get("arguments"),dict) for c in res["tool_calls"]):
        raise LLMError("Argumen alat dari model tidak dapat diurai dengan aman; panggilan tidak dijalankan. Coba model lain.")
    return res


async def _chat_ollama(messages, tools, model, on_token, fmt, temperature, num_ctx, max_tokens=None,
                       threads=None) -> dict:
    base = db.setting("ollama_url").rstrip("/")
    native = bool(tools) and model not in _no_native_tools
    msgs = messages if native or not tools else to_text_mode(messages, tools)
    if model in _no_think_param and msgs and msgs[-1]["role"] == "user":
        # model yang tidak menerima think=false: minta lewat teks (dipahami Qwen3/MiniCPM)
        msgs = msgs[:-1] + [dict(msgs[-1], content=msgs[-1]["content"] + "\n/no_think")]
    body = {
        "model": model,
        "messages": msgs,
        "stream": True,
        "keep_alive": db.setting("keep_alive") or "30m",
        "options": {"num_ctx": int(num_ctx or db.setting("num_ctx") or 8192), "temperature": temperature,
                    # batas panjang jawaban: model kecil kadang menulis tanpa henti dan menahan antrean
                    "num_predict": int(max_tokens or db.setting("max_tokens") or 900)},
    }
    if threads:
        body["options"]["num_thread"] = threads
    if db.setting("tool_mode") == "text" and native:
        native = False
        body["messages"] = to_text_mode(messages, tools)
    if native:
        body["tools"] = tools
    if fmt:
        body["format"] = fmt
    if model not in _no_think_param:
        body["think"] = False

    t0 = time.time()
    content, calls, stats = "", [], {}
    held = ""  # teks yang ditahan karena mungkin panggilan alat
    try:
        async with session().post(f"{base}/api/chat", json=body,
                                  # memuat model dari disk + membaca prompt panjang di CPU 2 core bisa >3 menit
                                  timeout=aiohttp.ClientTimeout(total=900, sock_read=480)) as r:
            if r.status != 200:
                err = await r.text()
                if native and ("does not support tools" in err or "invalid tool call" in err.lower() or "tool call arguments" in err.lower()):
                    _no_native_tools.add(model)
                    return await _chat_ollama(messages, tools, model, on_token, fmt, temperature, num_ctx, max_tokens, threads)
                if "think" in err.lower() and "think" in body:
                    _no_think_param.add(model)
                    return await _chat_ollama(messages, tools, model, on_token, fmt, temperature, num_ctx, max_tokens, threads)
                if "not found" in err:
                    raise LLMError(f"Model '{model}' belum diunduh. Unduh dulu di halaman Model.")
                raise LLMError(f"Ollama menolak ({r.status}): {err[:300]}")
            async for line in r.content:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    if native and ("invalid tool call" in chunk["error"].lower() or "tool call arguments" in chunk["error"].lower()) and not content and not calls:
                        _no_native_tools.add(model)
                        return await _chat_ollama(messages, tools, model, on_token, fmt, temperature, num_ctx, max_tokens, threads)
                    raise LLMError(chunk["error"])
                msg = chunk.get("message") or {}
                if msg.get("tool_calls"):
                    for c in msg["tool_calls"]:
                        f = c.get("function", {})
                        args = f.get("arguments", {})
                        if isinstance(args, str):
                            args = _loads(args)
                        calls.append({"name": f.get("name"), "arguments": args})
                piece = msg.get("content") or ""
                if piece:
                    content += piece
                    if on_token and not tools_suspect(content):
                        if held:
                            piece, held = held + piece, ""
                        await on_token(piece)
                    elif on_token:
                        held += piece
                if chunk.get("done"):
                    stats = {
                        "usage_reported": "prompt_eval_count" in chunk and "eval_count" in chunk, "prompt_tokens": chunk.get("prompt_eval_count", 0),
                        "tokens": chunk.get("eval_count", 0),
                        "seconds": round(time.time() - t0, 1),
                        "tok_per_sec": round(chunk.get("eval_count", 0) / max(chunk.get("eval_duration", 1) / 1e9, 1e-6), 1),
                        "prompt_tok_per_sec": round(chunk.get("prompt_eval_count", 0) / max(chunk.get("prompt_eval_duration", 1) / 1e9, 1e-6), 1),
                    }
    except asyncio.TimeoutError:
        raise LLMError("Model terlalu lama menjawab (8 menit tanpa balasan). Server mungkin sedang sangat sibuk "
                       "atau RAM penuh. Coba lagi sebentar lagi, atau pakai model yang lebih kecil.")
    except aiohttp.ClientError as e:
        raise LLMError(f"Tidak bisa menghubungi Ollama di {base}: {e}")
    return {"content": content, "tool_calls": calls, "stats": stats}


def tools_suspect(text: str) -> bool:
    """Jawaban yang diawali tanda-tanda panggilan alat jangan dialirkan ke layar."""
    s = text.lstrip()
    if not s:
        return True
    return s[0] in "<{[`" or bool(re.match(r"^\w+\(", s)) or s.startswith("<think")


async def _chat_online(messages, tools, temperature, fmt, local=False, model_override=None, max_tokens=None, on_token=None) -> dict:
    backend = active_backend()
    base = db.setting("compatible_base" if local else "online_base").rstrip("/")
    if local and backend == "router":
        from . import router
        if not model_override or model_override in ("smart","auto:smart","local","online"):
            raise LLMError("Pilih model 9router dari provider terhubung di Koneksi. Model Smart Router/FreeLLMAPI tidak bisa digunakan sebagai ID 9router.")
        base = router.base() + "/v1"
    elif local and backend == "local":
        from . import runtime_status
        status = await runtime_status.state()
        if not status["ready"]:
            raise LLMError(status["message"] + " Buka menu AI untuk progres/log; tidak perlu menghapus data lama.")
        import os
        base = os.environ.get("LOCAL_API_BASE", "http://local:8080/v1")
    if local and backend == "freellmapi":
        from . import free_router
        base = free_router.base() + "/v1"
        await free_router.ensure_key()
    key = "" if local and backend == "local" else db.setting("compatible_key" if local else "online_key")
    if local and backend == "freellmapi": key = db.setting("freellmapi_key")
    model = model_override if local else (model_override or db.setting("online_model"))
    if local and backend == "local": model = db.setting("local_model_id") or "qwenpaw-2b"
    if not (base and model and (local or key)):
        raise LLMError("API online belum diatur (Pengaturan → Otak online).")
    msgs, pending = [], []
    for i, m in enumerate(messages):
        m = dict(m)
        if m["role"] == "assistant" and m.get("tool_calls"):
            tc = []
            for j, c in enumerate(m["tool_calls"]):
                cid = f"call_{i}_{j}"
                pending.append(cid)
                tc.append({"id": cid, "type": "function",
                           "function": {"name": c["function"]["name"], "arguments": json.dumps(c["function"]["arguments"])}})
            m = {"role": "assistant", "content": m.get("content") or "", "tool_calls": tc}
        elif m["role"] == "tool":
            m = {"role": "tool", "tool_call_id": pending.pop(0) if pending else "call_x", "content": m["content"]}
        msgs.append(m)
    text_tools = local and backend not in ("router", "freellmapi") and db.setting("tool_mode") != "native"
    if text_tools:
        msgs = to_text_mode(messages, tools)
    body = {"model": model, "messages": msgs, "temperature": temperature,
            "max_tokens": int(max_tokens or db.setting("max_tokens") or 900)}
    if local and backend == "local":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    if tools and not text_tools:
        body["tools"] = tools
    if fmt:
        body["response_format"] = fmt if isinstance(fmt,dict) else {"type": "json_object"}
    # Stream ordinary answers/code so the first real token reaches the UI immediately.
    # Native tool calls retain the complete JSON response before argument validation.
    if not tools:
        body['stream'] = True
        body['stream_options'] = {'include_usage': True}
    t0 = time.time()
    try:
        for usage_attempt in range(2):
            async with session().post(f"{base}/chat/completions", json=body,
                                      headers={"Authorization": f"Bearer {key}"} if key else {},
                                      timeout=aiohttp.ClientTimeout(total=360 if local and backend == 'local' else 180, sock_read=90)) as r:
                if r.status==400 and body.get('stream_options'):
                    rejection=await r.text()
                    if 'stream_options' in rejection or 'include_usage' in rejection:
                        body.pop('stream_options',None)
                        continue
                    raise LLMError('Provider menolak permintaan: '+rejection[:200])
                if body.get('stream') and 'text/event-stream' in r.headers.get('Content-Type',''):
                    parts, usage, served, finish_reason = [], {}, '', None
                    async for line in r.content:
                        line = line.decode('utf-8').strip()
                        if not line.startswith('data:'): continue
                        payload = line[5:].strip()
                        if payload == '[DONE]': break
                        chunk = json.loads(payload)
                        if chunk.get('error'): raise LLMError(str(chunk['error'])[:300])
                        served = chunk.get('model') or served
                        usage = chunk.get('usage') or usage
                        for choice in chunk.get('choices',[]):
                            finish_reason = choice.get('finish_reason') or finish_reason
                            content = choice.get('delta',{}).get('content') or ''
                            if content:
                                parts.append(content)
                                if on_token: await on_token(content)
                    if not parts: raise LLMError('Model tidak mengembalikan teks. Periksa model/provider yang dipilih.')
                    data = {'model':served, 'usage':usage, 'choices':[{'message':{'content':''.join(parts)},'finish_reason':finish_reason}]}
                else:
                    data = await r.json(content_type=None)
                served_model = r.headers.get("X-Routed-Via") or data.get("model", "")
            break
    except asyncio.TimeoutError:
        raise LLMError('Model melewati batas waktu. Coba permintaan lebih pendek atau model/API lebih cepat.')
    except Exception as e:
        raise LLMError(f"API gagal: {str(e) or type(e).__name__}")
    if "choices" not in data and "API key required" in str(data):
        raise LLMError("9router belum memiliki API key yang valid. Buka menu AI & 9router lalu tekan Hubungkan otomatis. Jika masih gagal, perbarui pemasang VPS.")
    if not data.get("choices"):
        raise LLMError(f"API online menolak: {str(data)[:300]}")
    msg = data["choices"][0]["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        arguments=c["function"].get("arguments") or {}
        calls.append({"name": c["function"]["name"], "arguments": arguments if isinstance(arguments,dict) else _loads(arguments)})
    usage = data.get("usage", {})
    return {"content": msg.get("content") or "", "tool_calls": calls,
            "stats": {"usage_reported": "prompt_tokens" in usage and "completion_tokens" in usage, "tokens": usage.get("completion_tokens", 0), "prompt_tokens": usage.get("prompt_tokens", 0),
                      "seconds": round(time.time() - t0, 1), "served_model": served_model,
                      "finish_reason": data["choices"][0].get("finish_reason")}}


# ---------- manajemen model di Ollama ----------

async def ollama_get(path: str):
    base = db.setting("ollama_url").rstrip("/")
    async with session().get(f"{base}{path}", timeout=aiohttp.ClientTimeout(total=15)) as r:
        return await r.json(content_type=None)


async def ollama_post(path: str, body: dict, timeout: float = 60):
    base = db.setting("ollama_url").rstrip("/")
    async with session().post(f"{base}{path}", json=body, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
        return await r.json(content_type=None)


async def is_loaded(model: str) -> bool:
    try:
        ps = await ollama_get("/api/ps")
        return any(model in (m.get("name"), m.get("model")) or m.get("name", "").startswith(model + ":")
                   for m in ps.get("models", []))
    except Exception:
        return True  # tidak tahu: jangan tampilkan pesan memuat


async def unload_except(keep: str):
    """Lepas semua model kecuali satu (dipakai sebelum model penglihatan dimuat saat RAM tipis)."""
    try:
        ps = await ollama_get("/api/ps")
        for m in ps.get("models", []):
            if m["name"] != keep and m.get("model") != keep:
                await ollama_post("/api/generate", {"model": m["name"], "keep_alive": 0})
    except Exception:
        pass


async def unload(model: str | None = None):
    """Lepas model dari RAM (misalnya sebelum menyalakan Chromium)."""
    try:
        ps = await ollama_get("/api/ps")
        for m in ps.get("models", []):
            if model is None or m["name"] == model:
                await ollama_post("/api/generate", {"model": m["name"], "keep_alive": 0})
    except Exception:
        pass


async def pull(model: str):
    """Unduh model; hasilkan progres (status, persen)."""
    base = db.setting("ollama_url").rstrip("/")
    async with session().post(f"{base}/api/pull", json={"model": model, "stream": True},
                              timeout=aiohttp.ClientTimeout(total=None, sock_read=900)) as r:
        async for line in r.content:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("error"):
                raise LLMError(d["error"])
            pct = None
            if d.get("total"):
                pct = round(100 * d.get("completed", 0) / d["total"], 1)
            yield d.get("status", ""), pct
