import asyncio
import json

from sih.server import mcp


def call(name, args=None):
    res = asyncio.run(mcp.call_tool(name, args or {}))
    if getattr(res, "structuredContent", None):
        return res.structuredContent
    return json.loads(res.content[0].text)


def test_tools_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"search_problem_statements", "get_problem_statement", "list_facets", "refresh_problem_statements"}


def test_search_tool():
    d = call("search_problem_statements", {"query": "ai", "sort": "ideas", "desc": True, "limit": 1})
    assert d["total"] == 2 and d["returned"] == 1
    assert d["results"][0]["ps_number"] == "SIH1010"


def test_search_deadline_and_full_description():
    d = call("search_problem_statements", {"deadline_from": "2026-10-28", "full_description": True})
    assert [r["ps_number"] for r in d["results"]] == ["SIH1001"]
    assert d["results"][0]["description"] == "Use drones and AI for crops."


def test_get_tool():
    assert call("get_problem_statement", {"ps_number": "SIH1002"})["title"] == "Satellite telemetry parser"
    assert "error" in call("get_problem_statement", {"ps_number": "nope"})


def test_facets_tool():
    assert call("list_facets")["total"] == 3
    assert call("list_facets", {"include_closed": True})["total"] == 4


def test_refresh_tool():
    d = call("refresh_problem_statements")
    assert d["count"] == 4 and d["cached"] is True


def test_closed_reported_as_null_and_flagged():
    d = call("get_problem_statement", {"ps_number": "SIH1002"})
    assert d["ideas"] is None and d["closed"] is True
    d = call("search_problem_statements", {"include_closed": True})
    assert [r["ps_number"] for r in d["results"]][-1] == "SIH1002"  # closed come last
    d = call("search_problem_statements", {"max_ideas": 100, "include_closed": True})
    assert "SIH1002" not in [r["ps_number"] for r in d["results"]]


def test_closed_hidden_by_default_and_reported():
    d = call("search_problem_statements", {})
    assert "SIH1002" not in [r["ps_number"] for r in d["results"]] and d["closed_hidden"] == 1
    d = call("search_problem_statements", {"include_closed": True})
    assert d["total"] == 4 and "closed_hidden" not in d


def test_relevance_default_with_query():
    d = call("search_problem_statements", {"query": "portal"})
    assert d["results"][0]["ps_number"] == "SIH1003"
