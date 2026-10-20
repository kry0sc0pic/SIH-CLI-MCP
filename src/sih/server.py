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
    sort: str | None = None,
    desc: bool = False,
    limit: int = 20,
    offset: int = 0,
    full_description: bool = False,
    include_closed: bool = False,
) -> dict:
    """Search/filter/sort problem statements.

    query: free text, ranked by relevance (title weighs most; handles plurals, typos, prefixes and related words like
    farming/agriculture/crop). Statements matching only some terms are included but rank lower.
    organization/category/theme/department: case-insensitive substring filters (category is e.g. 'Software' or 'Hardware').
    min_ideas/max_ideas: filter by number of ideas already submitted (low = less competition). Statements with closed
    submissions have no count (ideas is null, closed is true): they are excluded by these filters and sorted last when sorting by ideas.
    open_only: exclude statements whose deadline has passed.
    deadline_from/deadline_to: inclusive ISO dates (YYYY-MM-DD) bounding the idea-submission deadline.
    sort: relevance (default with a query), ps_number (default otherwise), title, organization, category, theme, ideas, deadline.
    include_closed: closed statements (submissions closed, no idea count) are hidden by default; when included they
    always come after open ones. closed_hidden in the result says how many were left out.
    Descriptions are truncated unless full_description is true.
    """
    total, items = core.search(query, organization, category, theme, department, max_ideas, min_ideas, open_only, deadline_from, deadline_to, sort, desc, limit, offset, include_closed=include_closed)
    rows = [p.summary(10**9 if full_description else 240) for p in items]
    out = {"total": total, "offset": offset, "returned": len(rows), "results": rows}
    if not include_closed:
        out["closed_hidden"] = core.hidden_closed(
            query=query, organization=organization, category=category, theme=theme, department=department,
            max_ideas=max_ideas, min_ideas=min_ideas, open_only=open_only, deadline_from=deadline_from, deadline_to=deadline_to,
        )
    return out


@mcp.tool()
def get_problem_statement(ps_number: str) -> dict:
    """Full details for one problem statement by PS number (e.g. 'SIH26265') or numeric id ('26265')."""
    p = core.get(ps_number)
    return p.summary(10**9) if p else {"error": f"{ps_number} not found"}


@mcp.tool()
def list_facets(include_closed: bool = False) -> dict:
    """Counts of problem statements per organization, category and theme (open ones only unless include_closed)."""
    return core.facets(include_closed)


@mcp.tool()
def refresh_problem_statements() -> dict:
    """Re-download the problem statements from sih.gov.in (cache otherwise lasts 6 hours)."""
    items = core.refresh()
    return {"count": len(items), **core.cache_info()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
