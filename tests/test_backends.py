"""Backend contract tests use a real local HTTP server, no model required."""
import json

import pytest
from aiohttp import web
from app import db, llm, tools


@pytest.mark.asyncio
async def test_ollama_invalid_json_retries_text_mode(monkeypatch):
    monkeypatch.setattr(llm, "_session", None)
    bodies = []
    async def handler(request):
        body = await request.json()
        bodies.append(body)
        if "tools" in body:
            return web.json_response({"error": 'llama-server returned invalid tool call arguments for "web_search": unexpected end of JSON input'}, status=500)
        return web.Response(text=json.dumps({"message": {"content": '<tool>{"name":"web_search","arguments":{"query":"emas"}}</tool>'}, "done": True}) + "\n")
    app = web.Application()
    app.router.add_post("/api/chat", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    original = db.setting
    monkeypatch.setattr(db, "setting", lambda key: {"ollama_url": f"http://127.0.0.1:{port}", "tool_mode": "native", "dns_aman": "0"}.get(key, original(key)))
    model = "regression-json-test"
    llm._no_native_tools.discard(model)
    try:
        res = await llm._chat_ollama([{"role":"system", "content":"Use tools"}, {"role":"user","content":"harga emas"}], [tools.REGISTRY["web_search"].schema()], model, None, None, 0.1, 2048)
        calls, _ = llm.extract_tool_calls(res["content"], {"web_search"})
        assert calls[0]["arguments"] == {"query": "emas"}
        assert len(bodies) == 2 and "tools" not in bodies[1]
        assert model in llm._no_native_tools
    finally:
        await runner.cleanup()
        if llm._session:
            await llm._session.close()
        llm._session = None


@pytest.mark.asyncio
async def test_compatible_without_key_respects_token_limit(monkeypatch):
    monkeypatch.setattr(llm, "_session", None)
    bodies = []
    async def handler(request):
        assert "Authorization" not in request.headers
        bodies.append(await request.json())
        return web.json_response({"choices": [{"message": {"content": "Halo"}}]})
    app = web.Application()
    app.router.add_post("/v1/chat/completions", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    original = db.setting
    monkeypatch.setattr(db, "setting", lambda key: {"compatible_base": f"http://127.0.0.1:{port}/v1", "compatible_key": "", "tool_mode": "text", "dns_aman": "0"}.get(key, original(key)))
    try:
        result = await llm._chat_online([{"role":"system","content":"hello"}], [tools.REGISTRY["web_search"].schema()], 0.1, None, local=True, model_override="combo", max_tokens=75)
        assert result["content"] == "Halo"
        assert bodies[0]["max_tokens"] == 75 and bodies[0]["model"] == "combo"
        assert "tools" not in bodies[0]
    finally:
        await runner.cleanup()
        if llm._session:
            await llm._session.close()
        llm._session = None


def test_reject_bad_arguments():
    assert tools.validate_arguments("web_search", None)
    assert tools.validate_arguments("web_search", {})
    assert tools.validate_arguments("web_search", {"query": 123})
    assert tools.validate_arguments("web_search", {"query": "  "})
    assert tools.validate_arguments("web_search", {"query": "emas"}) is None
    assert llm._norm_call({"name": "web_search", "arguments": '{"query":'}, {"web_search"})["arguments"] is None


@pytest.mark.asyncio
async def test_mcp_stdio_allowlist_and_execution(monkeypatch, tmp_path):
    import sys
    from app import config, mcp_bridge
    script = tmp_path / "server.py"
    script.write_text('from mcp.server.fastmcp import FastMCP\nm = FastMCP("test")\n@m.tool()\ndef echo(text: str) -> str:\n    return text\n@m.tool()\ndef forbidden() -> str:\n    return "forbidden"\nm.run()\n')
    (tmp_path / "mcp.json").write_text(json.dumps({"servers": {"test": {"command": sys.executable, "args": [str(script)], "allow_tools": ["echo"], "read_only_tools": ["echo"]}}}))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    try:
        assert await mcp_bridge.register() == []
        registered = tools.REGISTRY["mcp_test_echo"]
        assert "mcp_test_forbidden" not in tools.REGISTRY
        assert registered.danger is None
        assert tools.validate_arguments("mcp_test_echo", {})
        output = await registered.fn(None, text="verified")
        assert output.splitlines()[0] == "verified"
        assert json.loads(output.splitlines()[1]) == {"result": "verified"}
    finally:
        tools.REGISTRY.pop("mcp_test_echo", None)


@pytest.mark.asyncio
async def test_unconfirmed_reflection_does_not_promote_skill(monkeypatch):
    from app import memory
    async def fake(*args, **kwargs):
        return {"content": json.dumps({"success": True, "skill": {"name": "unverified procedure", "steps": ["web_search", "write_file"]}})}
    monkeypatch.setattr(llm, "chat", fake)
    result = await memory.reflect({"id": "test", "memory_scope": "shared"}, [{"role": "user", "content": "Cari lalu simpan"}], ["web_search", "write_file"])
    assert result["skill"] is None
