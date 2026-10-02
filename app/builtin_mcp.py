"""Bundled read-only MCP: local hardware and owner-approved skill search."""
import json, sqlite3
from mcp.server.fastmcp import FastMCP
from . import config, local_models
server = FastMCP('Agen Mini local helpers')
@server.tool(annotations={'readOnlyHint':True})
def hardware() -> dict:
    """Read detected VPS CPU/RAM and the curated local model recommendations."""
    return local_models.catalogue()
@server.tool(annotations={'readOnlyHint':True})
def search_skills(query: str) -> list[dict]:
    """Find active shared procedures, read only, without accessing account credentials."""
    conn=sqlite3.connect(config.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    try:
        pattern='%'+query[:120]+'%'
        rows=conn.execute("SELECT name,when_to_use,steps FROM skills WHERE active=1 AND scope='shared' AND (name LIKE ? OR when_to_use LIKE ?) LIMIT 5",(pattern,pattern)).fetchall()
        return [dict(r) for r in rows]
    finally:conn.close()
if __name__=='__main__':server.run(transport='stdio')
