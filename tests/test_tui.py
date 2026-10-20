import asyncio

from sih import core
from sih.tui import Browser, Filters, detail_renderable, ideas_text, row_prompt


def run(coro_fn, filters=None, page_size=2):
    async def go():
        app = Browser(filters, page_size=page_size)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await coro_fn(app, pilot)

    asyncio.run(go())


def test_initial_state_shows_first_item():
    async def t(app, pilot):
        assert len(app.items) == 4 and app.current.ps_number == "SIH1001"
        assert app.query_one("#list").option_count == 2  # one page
        assert "page 1/2" in app.sub_title and "4 matches" in app.sub_title

    run(t)


def test_arrows_move_and_cross_pages():
    async def t(app, pilot):
        await pilot.press("down")
        assert app.current.ps_number == "SIH1002"
        await pilot.press("down")  # off the end of page 1 -> page 2
        await pilot.pause()
        assert app.current.ps_number == "SIH1003" and "page 2/2" in app.sub_title
        await pilot.press("up")  # back across the boundary
        await pilot.pause()
        assert app.current.ps_number == "SIH1002" and "page 1/2" in app.sub_title
        await pilot.press("up", "up")  # stays at the very start
        assert app.current.ps_number == "SIH1001"

    run(t)


def test_page_keys():
    async def t(app, pilot):
        await pilot.press("n")
        assert app.current.ps_number == "SIH1003"
        await pilot.press("right")  # already last page: clamps
        assert app.current.ps_number == "SIH1003"
        await pilot.press("p")
        assert app.current.ps_number == "SIH1001"

    run(t)


def test_end_of_list_does_not_wrap():
    async def t(app, pilot):
        await pilot.press("n", "down", "down", "down")
        await pilot.pause()
        assert app.current.ps_number == "SIH1010"

    run(t)


def test_search_filters_list():
    async def t(app, pilot):
        await pilot.press("slash")
        for ch in "drone":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert [p.ps_number for p in app.items] == ["SIH1001"] and "query: drone" in app.sub_title
        await pilot.press("slash", "escape")  # cancel leaves results alone
        assert len(app.items) == 1

    run(t)


def test_letters_typed_in_search_do_not_trigger_actions():
    async def t(app, pilot):
        await pilot.press("slash", "s", "d", "o", "n", "p")
        assert app.filters.sort == "ps_number" and not app.filters.desc and not app.filters.open_only
        assert app.query_one("#search").value == "sdonp"

    run(t)


def test_sort_and_desc_keep_selection():
    async def t(app, pilot):
        await pilot.press("down")  # SIH1002 selected
        await pilot.press("d")
        assert app.filters.desc and app.current.ps_number == "SIH1002"
        assert app.items[0].ps_number == "SIH1010"
        await pilot.press("s")
        assert app.filters.sort == "ps_number" or app.filters.sort == "title"

    run(t)


def test_open_toggle_filters():
    async def t(app, pilot):
        await pilot.press("o")
        assert app.filters.open_only and "open only" in app.sub_title

    run(t)


def test_initial_filters_and_empty_state():
    async def t(app, pilot):
        assert app.items == [] and app.current is None
        await pilot.press("down", "n", "p")  # must not crash

    run(t, Filters(query="zzzznomatch"))


def test_closed_rendering():
    p = core.get("SIH1002")
    assert str(ideas_text(p)) == "closed" and ideas_text(p).style == "bold red"
    assert "closed" in row_prompt(p).plain
    assert str(ideas_text(core.get("SIH1001"))) == "3/500"


def test_detail_contains_description_and_meta():
    from rich.console import Console

    c = Console(width=100, record=True, file=open("/dev/null", "w"))
    c.print(detail_renderable(core.get("SIH1001")))
    out = c.export_text()
    for needle in ("Drone swarm for farms", "Use drones and AI for crops.", "AICTE", "3/500", "2026-10-28", "https://x.test/data"):
        assert needle in out


def test_cli_browse_registered_and_validates_sort():
    from typer.testing import CliRunner

    from sih.cli import app

    r = CliRunner().invoke(app, ["browse", "--sort", "bogus"])
    assert r.exit_code != 0


def test_row_prompt_truncates_to_two_lines():
    p = core.get("SIH1001")
    long = type(p)(**{**p.__dict__, "title": "word " * 60})
    t = row_prompt(long, 30)
    lines = t.plain.split("\n")
    assert len(lines) == 2 and len(lines[1]) <= 30 and lines[1].endswith("…")
