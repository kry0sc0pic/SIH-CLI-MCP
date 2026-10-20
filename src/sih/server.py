"""MCP server exposing SIH problem statements."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import core

mcp = MCPServer(
    "sih",
    instructions=(
        "Smart India Hackathon 2026 problem statements. Use list_facets to see valid organizations/categories/themes, "
        "search_problem_statements to filter and sort, get_problem_statement for the full description."
    ),
)


@mcp.tool()
def search_problem_statements(
    query: str | None = None,
    organization: str | None = None,
    category: str | None = None,
    theme: str | None = None,
    department: str | None = None,
    min_ideas: int | None = None,
    max_ideas: int | None = None,
    open_only: bool = False,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    sort: str = "ps_number",
    desc: bool = False,
    limit: int = 20,
    offset: int = 0,
    full_description: bool = False,
) -> dict:
    """Search/filter/sort problem statements.

    query: space-separated terms, all must match title/description/org/theme (ranked by relevance when sort is the default).
    organization/category/theme/department: case-insensitive substring filters (category is e.g. 'Software' or 'Hardware').
    min_ideas/max_ideas: filter by number of ideas already submitted (low = less competition). Statements with closed
    submissions have no count (ideas is null, closed is true): they are excluded by these filters and sorted last when sorting by ideas.
    open_only: exclude statements whose deadline has passed.
    deadline_from/deadline_to: inclusive ISO dates (YYYY-MM-DD) bounding the idea-submission deadline.
    sort: one of ps_number, title, organization, category, theme, ideas, deadline.
    Descriptions are truncated unless full_description is true.
    """
    total, items = core.search(query, organization, category, theme, department, max_ideas, min_ideas, open_only, deadline_from, deadline_to, sort, desc, limit, offset)
    rows = [p.summary(10**9 if full_description else 240) for p in items]
    return {"total": total, "offset": offset, "returned": len(rows), "results": rows}


@mcp.tool()
def get_problem_statement(ps_number: str) -> dict:
    """Full details for one problem statement by PS number (e.g. 'SIH26265') or numeric id ('26265')."""
    p = core.get(ps_number)
    return p.summary(10**9) if p else {"error": f"{ps_number} not found"}


@mcp.tool()
def list_facets() -> dict:
    """Counts of problem statements per organization, category and theme."""
    return core.facets()


@mcp.tool()
def refresh_problem_statements() -> dict:
    """Re-download the problem statements from sih.gov.in (cache otherwise lasts 6 hours)."""
    items = core.refresh()
    return {"count": len(items), **core.cache_info()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
