"""Run the real server as a subprocess and talk MCP over stdio (no network: the cache is pre-seeded)."""

import asyncio
import json
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sih import core


def test_server_over_stdio(tmp_path):
    core.refresh()  # fixture-mocked fetch writes the cache
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    shutil.copy(core.CACHE_FILE, cache_dir / "problem_statements.json")

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "sih.server"], env={"SIH_CACHE_DIR": str(cache_dir), "SIH_URL": "http://127.0.0.1:9/never"})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()

                async def call(name, args=None):
                    res = await s.call_tool(name, args or {})
                    return res, (json.loads(res.content[0].text) if not res.is_error else res.content[0].text)

                tools = {t.name for t in (await s.list_tools()).tools}
                assert tools == {"search_problem_statements", "get_problem_statement", "list_facets", "refresh_problem_statements"}

                _, d = await call("search_problem_statements", {"query": "drones"})
                assert [x["ps_number"] for x in d["results"]] == ["SIH1001"] and d["closed_hidden"] == 0
                _, d = await call("search_problem_statements", {"include_closed": True})
                assert [x["ps_number"] for x in d["results"]][-1] == "SIH1002"
                assert d["results"][-1]["ideas"] is None and d["results"][-1]["closed"] is True
                _, d = await call("get_problem_statement", {"ps_number": "1010"})
                assert d["title"] == "Cyber threat triage"
                _, d = await call("list_facets")
                assert d["total"] == 3 and d["closed_hidden"] == 1

                res, text = await call("search_problem_statements", {"sort": "bogus"})
                assert res.is_error and "invalid sort" in text

    asyncio.run(go())
