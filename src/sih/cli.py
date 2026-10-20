"""sih CLI: same capabilities as the MCP server."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import core

app = typer.Typer(help="Browse SIH problem statements.", no_args_is_help=True)
console = Console()


@app.command()
def refresh() -> None:
    """Re-download from sih.gov.in."""
    items = core.refresh()
    console.print(f"Fetched {len(items)} problem statements -> {core.CACHE_FILE}")


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Terms, all must match"),
    org: Optional[str] = typer.Option(None, "--org", "-o"),
    category: Optional[str] = typer.Option(None, "--category", "-c"),
    theme: Optional[str] = typer.Option(None, "--theme", "-t"),
    department: Optional[str] = typer.Option(None, "--dept"),
    min_ideas: Optional[int] = typer.Option(None, "--min-ideas"),
    max_ideas: Optional[int] = typer.Option(None, "--max-ideas"),
    open_only: bool = typer.Option(False, "--open"),
    deadline_from: Optional[str] = typer.Option(None, "--from", help="YYYY-MM-DD"),
    deadline_to: Optional[str] = typer.Option(None, "--to", help="YYYY-MM-DD"),
    sort: str = typer.Option("ps_number", "--sort", "-s", help="/".join(core.SORT_KEYS)),
    desc: bool = typer.Option(False, "--desc"),
    limit: int = typer.Option(20, "--limit", "-n"),
    offset: int = typer.Option(0, "--offset"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Filter and sort problem statements."""
    total, items = core.search(query, org, category, theme, department, max_ideas, min_ideas, open_only, deadline_from, deadline_to, sort, desc, limit, offset)
    if as_json:
        console.print_json(json.dumps({"total": total, "results": [p.summary() for p in items]}))
        return
    t = Table(title=f"{len(items)} of {total}")
    for c in ("PS", "Org", "Title", "Cat", "Theme", "Ideas", "Deadline"):
        t.add_column(c, overflow="fold")
    for p in items:
        t.add_row(p.ps_number, p.organization, p.title, p.category, p.theme, f"{p.ideas}/{p.ideas_cap or '-'}", p.deadline or "-")
    console.print(t)


@app.command()
def show(ps_number: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Full details for one problem statement."""
    p = core.get(ps_number)
    if not p:
        raise typer.Exit(f"{ps_number} not found")
    if as_json:
        console.print_json(json.dumps(p.summary(10**9)))
        return
    console.print(f"[bold]{p.ps_number}[/bold] {p.title}")
    console.print(f"{p.organization} / {p.department} | {p.category} | {p.theme} | ideas {p.ideas}/{p.ideas_cap} | deadline {p.deadline}")
    for label, v in (("Dataset", p.dataset_links), ("YouTube", p.youtube), ("Contact", p.contact)):
        if v:
            console.print(f"{label}: {v}")
    console.print()
    console.print(p.description, markup=False)


@app.command()
def facets() -> None:
    """Counts per organization, category and theme."""
    f = core.facets()
    console.print(f"Total: {f['total']}")
    for k in ("category", "theme", "organization"):
        t = Table(title=k)
        t.add_column(k)
        t.add_column("n", justify="right")
        for name, n in f[k]:
            t.add_row(name, str(n))
        console.print(t)


@app.command()
def mcp() -> None:
    """Run the MCP server over stdio."""
    from .server import main

    main()


if __name__ == "__main__":
    app()
