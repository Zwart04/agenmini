"""Optional MCP connections, loaded from an owner-controlled file, never model output."""
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager

from . import config, tools


@asynccontextmanager
async def connection(server):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
    if server.get("url"):
        headers = {k: os.path.expandvars(v) for k, v in server.get("headers", {}).items()}
        async with streamablehttp_client(server["url"], headers=headers) as (read, write, _):
            async with ClientSession(read, write) as client:
                await client.initialize()
                yield client
    else:
        params = StdioServerParameters(command=server["command"], args=server.get("args", []),
                                       env={**os.environ, **{k: os.path.expandvars(v) for k, v in server.get("env", {}).items()}})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                yield client


async def register():
    path = config.DATA_DIR / "mcp.json"
    if not path.exists():
        return []
    servers = json.loads(path.read_text(encoding="utf-8"))["servers"]
    errors = []
    for alias, server in servers.items():
        try:
            if not re.fullmatch(r"[a-zA-Z0-9_]{1,24}", alias):
                raise ValueError("Nama server tidak valid")
            async with asyncio.timeout(30):
                async with connection(server) as client:
                    response = await client.list_tools()
            allowed = set(server.get("allow_tools", []))
            readonly = set(server.get("read_only_tools", []))
            for remote in response.tools:
                if remote.name not in allowed:
                    continue
                name = f"mcp_{alias}_{remote.name}"
                if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
                    continue
                def bind(server_config, remote_name):
                    async def invoke(ctx, **arguments):
                        async with asyncio.timeout(90):
                            async with connection(server_config) as client:
                                result = await client.call_tool(remote_name, arguments=arguments)
                        text = "\n".join(getattr(c, "text", "") for c in result.content)
                        if result.structuredContent:
                            text += "\n" + json.dumps(result.structuredContent, ensure_ascii=False)
                        return ("Error: " if result.isError else "") + (text or "(tanpa keluaran teks)")
                    return invoke
                invoke = bind(server, remote.name)
                schema = remote.inputSchema
                danger = None if remote.name in readonly else lambda args: "alat MCP ini dapat mengubah data atau mengirim pesan"
                tools.REGISTRY[name] = tools.Tool(name, name, (remote.description or remote.name)[:1200],
                                                 schema.get("properties", {}), schema.get("required", []), invoke,
                                                 danger, schema)
        except Exception as exc:
            errors.append(f"{alias}: {type(exc).__name__}")
    return errors
