import json
import time

import pytest

from sih import core


def test_parse_fields(html):
    items = core.parse(html)
    assert len(items) == 4
    p = items[0]
    assert (p.ps_number, p.ps_id, p.organization) == ("SIH1001", "1001", "AICTE")
    assert p.title == "Drone swarm for farms"
    assert p.category == "Software"  # normalised from "software"
    assert (p.ideas, p.ideas_cap) == (3, 500)
    assert p.deadline == "2026-10-28"
    assert p.description == "Use drones and AI for crops."  # HTML comment ignored
    assert p.dataset_links == ["https://x.test/data"]
    assert p.youtube == "" and p.department == "Dept of AICTE"


def test_parse_edge_cases(html):
    items = core.parse(html)
    assert (items[1].ideas, items[1].ideas_cap, items[1].closed) == (None, None, True)  # no count when closed
    assert items[0].closed is False
    assert items[3].deadline is None


def test_parse_missing_table():
    with pytest.raises(RuntimeError):
        core.parse("<html></html>")


def test_refresh_writes_cache_and_load_uses_it(fetch_calls):
    core.refresh()
    assert core.CACHE_FILE.exists() and len(fetch_calls) == 1
    assert len(core.load()) == 4
    assert len(fetch_calls) == 1  # served from cache


def test_load_refetches_when_stale_or_forced(fetch_calls):
    core.refresh()
    data = json.loads(core.CACHE_FILE.read_text())
    data["fetched_at"] = time.time() - core.CACHE_TTL - 10
    core.CACHE_FILE.write_text(json.dumps(data))
    core.load()
    assert len(fetch_calls) == 2
    core.load(force=True)
    assert len(fetch_calls) == 3


def test_cache_info():
    assert core.cache_info() == {"cached": False}
    core.refresh()
    info = core.cache_info()
    assert info["cached"] and info["count"] == 4


def nums(**kw):
    total, items = core.search(**kw)
    return total, [p.ps_number for p in items]


def test_search_no_filters_sorted_numerically():
    # ps_number sort is numeric-aware: SIH1010 after SIH1003
    assert nums() == (4, ["SIH1001", "SIH1002", "SIH1003", "SIH1010"])


def test_search_filters():
    assert nums(category="hardware")[1] == ["SIH1002"]
    assert nums(organization="aicte")[1] == ["SIH1001", "SIH1003"]
    assert nums(theme="space")[1] == ["SIH1002"]
    assert nums(department="isro")[1] == ["SIH1002"]
    assert nums(max_ideas=3)[1] == ["SIH1001"]  # closed has no count, so excluded
    assert nums(min_ideas=7)[1] == ["SIH1003", "SIH1010"]


def test_search_query_word_matching():
    assert nums(query="ai")[1] == ["SIH1001", "SIH1010"]  # whole word: not AICTE, not "Tribal"
    assert nums(query="drone crops")[1] == ["SIH1001"]  # terms ANDed, description searched
    assert nums(query="tele")[1] == ["SIH1002"]  # prefix for longer terms
    assert nums(query="nothingmatches")[0] == 0


def test_search_query_ranks_title_first():
    # "ai" only appears in descriptions of both; a title hit must outrank a description-only hit
    assert nums(query="portal ai")[0] == 0
    assert nums(query="cyber")[1][0] == "SIH1010"
    total, items = core.search(query="threat tribal")
    assert total == 0
    # title match (3) + one hit beats description-only match
    assert nums(query="drone")[1] == ["SIH1001"]


def test_search_deadlines(monkeypatch):
    assert nums(deadline_from="2026-10-20")[1] == ["SIH1001", "SIH1010"]
    assert nums(deadline_to="2026-10-05")[1] == ["SIH1002"]  # undated excluded from upper bound
    assert nums(deadline_from="2026-10-06", deadline_to="2026-10-25")[1] == ["SIH1010"]


def test_open_only_excludes_past(monkeypatch):
    from datetime import datetime

    class D(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 20)

    monkeypatch.setattr(core, "datetime", D)
    assert nums(open_only=True)[1] == ["SIH1001", "SIH1003", "SIH1010"]  # undated stays; 10-05 dropped


def test_sort_and_pagination():
    assert nums(sort="ideas", desc=True)[1] == ["SIH1010", "SIH1003", "SIH1001", "SIH1002"]
    assert nums(sort="ideas")[1] == ["SIH1001", "SIH1003", "SIH1010", "SIH1002"]  # closed last either way
    assert nums(sort="title")[1][0] == "SIH1003"  # Campus portal
    assert nums(sort="deadline")[1][0] == "SIH1002"
    total, page = nums(limit=2, offset=1)
    assert total == 4 and page == ["SIH1002", "SIH1003"]


def test_bad_sort():
    with pytest.raises(ValueError):
        core.search(sort="bogus")


def test_get_variants():
    assert core.get("SIH1002").title == "Satellite telemetry parser"
    assert core.get("sih1002").ps_number == "SIH1002"
    assert core.get("1002").ps_number == "SIH1002"
    assert core.get("SIH9999") is None


def test_summary_truncates():
    p = core.get("SIH1001")
    assert p.summary(10)["description"].endswith("…") and len(p.summary(10)["description"]) == 10
    assert p.summary()["description"] == p.description


def test_facets():
    f = core.facets()
    assert f["total"] == 4
    assert dict(f["organization"])["AICTE"] == 2
    assert dict(f["category"]) == {"Software": 3, "Hardware": 1}
