"""Interactive browser: paginated list on the left, details on the right."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from . import core

SORTS = core.SORT_KEYS


@dataclass
class Filters:
    query: str | None = None
    organization: str | None = None
    category: str | None = None
    theme: str | None = None
    department: str | None = None
    min_ideas: int | None = None
    max_ideas: int | None = None
    open_only: bool = False
    deadline_from: str | None = None
    deadline_to: str | None = None
    sort: str = "ps_number"
    desc: bool = False
    extra: dict = field(default_factory=dict)


def ideas_text(p: core.PS) -> Text:
    if p.ideas is None:
        return Text("closed", style="bold red") if p.closed else Text("?")
    return Text(f"{p.ideas}/{p.ideas_cap}" if p.ideas_cap else str(p.ideas))


def row_prompt(p: core.PS, width: int = 0) -> Text:
    t = Text()
    t.append(p.ps_number, style="cyan")
    t.append("  ")
    t.append_text(ideas_text(p))
    t.append("\n")
    title = Text(" ".join(p.title.split()))
    if width > 0:  # one line per title keeps every row exactly two lines, so page size is predictable
        title.truncate(width, overflow="ellipsis")
    t.append_text(title)
    return t


def detail_renderable(p: core.PS) -> Group:
    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="dim", justify="right", no_wrap=True)
    meta.add_column()
    rows = [
        ("Organization", p.organization),
        ("Department", p.department or "-"),
        ("Category", p.category),
        ("Theme", p.theme),
        ("Ideas", ideas_text(p)),
        ("Deadline", p.deadline or "-"),
    ]
    if p.dataset_links:
        rows.append(("Dataset", "\n".join(p.dataset_links)))
    if p.youtube:
        rows.append(("YouTube", p.youtube))
    if p.contact:
        rows.append(("Contact", p.contact))
    for k, v in rows:
        meta.add_row(k, v if isinstance(v, Text) else Text(v))
    return Group(
        Text(p.title.strip(), style="bold"),
        Text(f"{p.ps_number}", style="cyan"),
        Text(),
        meta,
        Text(),
        Text("Description", style="bold underline"),
        Text(p.description or "(none)"),
    )


class PSList(OptionList):
    """Arrow keys run off either end of a page into the neighbouring page."""

    def action_cursor_down(self) -> None:
        if self.highlighted is not None and self.highlighted >= self.option_count - 1:
            self.app.action_step(1)
        else:
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.highlighted is not None and self.highlighted <= 0:
            self.app.action_step(-1)
        else:
            super().action_cursor_up()


class Browser(App):
    CSS = """
    #body { height: 1fr; }
    #list { width: 42%; height: 1fr; border-right: solid $primary; }
    #detail-pane { width: 1fr; padding: 0 2; }
    #search { dock: bottom; display: none; }
    #search.open { display: block; }
    """
    BINDINGS = [
        Binding("right,n", "page(1)", "Next page"),
        Binding("left,p", "page(-1)", "Prev page"),
        Binding("slash", "search", "Search"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("d", "toggle_desc", "Asc/Desc"),
        Binding("o", "toggle_open", "Open only"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, filters: Filters | None = None, page_size: int | None = None):
        super().__init__()
        self.filters = filters or Filters()
        self.fixed_page_size = page_size
        self.items: list[core.PS] = []
        self.cursor = 0  # index into self.items
        self.current: core.PS | None = None
        self._loading = False

    # --- layout -----------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield PSList(id="list")
            with VerticalScroll(id="detail-pane"):
                yield Static(id="detail")
        yield Input(placeholder="Search terms (Enter to apply, Esc to cancel)", id="search")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "SIH problem statements"
        self.query_one("#list").focus()
        self.reload()
        self.call_after_refresh(self.render_page)  # sizes are only known after the first layout

    def on_resize(self) -> None:
        if self.items:
            self.call_after_refresh(self.render_page)

    # --- data -------------------------------------------------------------
    @property
    def page_size(self) -> int:
        if self.fixed_page_size:
            return self.fixed_page_size
        return max(3, (self.query_one("#list").size.height or 20) // 2)  # two lines per row

    @property
    def pages(self) -> int:
        return max(1, -(-len(self.items) // self.page_size))

    def reload(self, keep: str | None = None) -> None:
        f = self.filters
        _, items = core.search(
            f.query, f.organization, f.category, f.theme, f.department, f.max_ideas, f.min_ideas,
            f.open_only, f.deadline_from, f.deadline_to, f.sort, f.desc, limit=10**6,
        )
        self.items = items
        self.cursor = next((i for i, p in enumerate(items) if p.ps_number == keep), 0)
        self.render_page()

    def render_page(self) -> None:
        lst = self.query_one("#list", PSList)
        size = self.page_size
        page = self.cursor // size
        start = page * size
        self._loading = True
        lst.clear_options()
        width = max(10, lst.size.width - 6)  # border + option padding + scrollbar
        lst.add_options([Option(row_prompt(p, width), id=str(start + i)) for i, p in enumerate(self.items[start : start + size])])
        if self.items:
            lst.highlighted = self.cursor - start
        self._loading = False
        self.show_detail()
        self.update_status()

    def show_detail(self) -> None:
        self.current = self.items[self.cursor] if self.items else None
        detail = self.query_one("#detail", Static)
        detail.update(detail_renderable(self.current) if self.current else Text("No matching problem statements."))
        self.query_one("#detail-pane").scroll_home(animate=False)

    def update_status(self) -> None:
        f = self.filters
        bits = [f"page {self.cursor // self.page_size + 1}/{self.pages}", f"{len(self.items)} matches", f"sort: {f.sort} {'desc' if f.desc else 'asc'}"]
        if f.query:
            bits.append(f"query: {f.query}")
        if f.open_only:
            bits.append("open only")
        self.sub_title = " · ".join(bits)

    # --- events / actions -------------------------------------------------
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._loading or event.option_id is None:
            return
        self.cursor = int(event.option_id)
        self.show_detail()
        self.update_status()

    def action_step(self, delta: int) -> None:
        target = self.cursor + delta
        if 0 <= target < len(self.items):
            self.cursor = target
            self.render_page()

    def action_page(self, delta: int) -> None:
        if not self.items:
            return
        size = self.page_size
        page = min(max(self.cursor // size + delta, 0), self.pages - 1)
        self.cursor = page * size
        self.render_page()

    def action_search(self) -> None:
        box = self.query_one("#search", Input)
        box.value = self.filters.query or ""
        box.add_class("open")
        box.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.filters.query = event.value.strip() or None
        self.close_search()
        self.reload()

    def on_key(self, event) -> None:
        if event.key == "escape" and self.query_one("#search").has_class("open"):
            self.close_search()
            event.stop()

    def close_search(self) -> None:
        self.query_one("#search").remove_class("open")
        self.query_one("#list").focus()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        # let letters/arrows reach the search box while typing
        if self.query_one("#search").has_class("open") and action in {"page", "cycle_sort", "toggle_desc", "toggle_open", "quit", "search"}:
            return False
        return True

    def _reload_keep(self) -> None:
        self.reload(keep=self.current.ps_number if self.current else None)

    def action_cycle_sort(self) -> None:
        self.filters.sort = SORTS[(SORTS.index(self.filters.sort) + 1) % len(SORTS)]
        self._reload_keep()

    def action_toggle_desc(self) -> None:
        self.filters.desc = not self.filters.desc
        self._reload_keep()

    def action_toggle_open(self) -> None:
        self.filters.open_only = not self.filters.open_only
        self._reload_keep()


def run(filters: Filters | None = None) -> None:
    Browser(filters).run()
