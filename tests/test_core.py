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
    kw.setdefault("include_closed", True)
    total, items = core.search(**kw)
    return total, [p.ps_number for p in items]


def test_search_no_filters_sorted_numerically():
    # ps_number sort is numeric-aware (SIH1010 after SIH1003); closed SIH1002 always last
    assert nums() == (4, ["SIH1001", "SIH1003", "SIH1010", "SIH1002"])
    assert nums(include_closed=False) == (3, ["SIH1001", "SIH1003", "SIH1010"])


def test_search_filters():
    assert nums(category="hardware")[1] == ["SIH1002"]
    assert nums(organization="aicte")[1] == ["SIH1001", "SIH1003"]
    assert nums(theme="space")[1] == ["SIH1002"]
    assert nums(department="isro")[1] == ["SIH1002"]
    assert nums(max_ideas=3)[1] == ["SIH1001"]  # closed has no count, so excluded
    assert nums(min_ideas=7)[1] == ["SIH1003", "SIH1010"]


def test_search_query_is_ranked_not_anded():
    total, got = nums(query="drone crops")
    assert got[0] == "SIH1001"  # matches both terms
    assert "SIH1010" not in got  # nothing in common


def test_search_query_matching_modes():
    assert nums(query="drones")[1] == ["SIH1001"]  # plural/stem
    assert nums(query="tele")[1] == ["SIH1002"]  # prefix
    assert nums(query="telemtry")[1] == ["SIH1002"]  # typo
    assert nums(query="agriculture")[1][0] == "SIH1001"  # synonym of farm/crop/agricultur via theme
    assert nums(query="nothingmatches")[0] == 0


def test_short_terms_are_exact():
    assert nums(query="ai")[1] == ["SIH1001", "SIH1010"]  # not AICTE, not "Tribal"


def test_title_hit_outranks_description_hit():
    # "triage" is in the title of SIH1010 and only in nothing else; "portal" title SIH1003
    assert nums(query="cyber")[1][0] == "SIH1010"
    assert nums(query="portal")[1][0] == "SIH1003"


def test_weak_partial_matches_are_cut():
    # "tribal" is only in SIH1003's description; adding a strongly matching term must not drag in noise
    got = nums(query="drone tribal")[1]
    assert got[0] == "SIH1001" and set(got) <= {"SIH1001", "SIH1003"}


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
    assert nums(sort="deadline")[1][0] == "SIH1010"  # earliest open deadline; closed SIH1002 last
    total, page = nums(limit=2, offset=1)
    assert total == 4 and page == ["SIH1003", "SIH1010"]  # SIH1002 is closed so sits last


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
    f = core.facets(include_closed=True)
    assert f["total"] == 4
    assert dict(f["organization"])["AICTE"] == 2
    assert dict(f["category"]) == {"Software": 3, "Hardware": 1}
    f = core.facets()
    assert f["total"] == 3 and f["closed_hidden"] == 1 and "Hardware" not in dict(f["category"])


def test_closed_hidden_by_default():
    total, items = core.search()
    assert total == 3 and "SIH1002" not in [p.ps_number for p in items]
    assert core.hidden_closed() == 1
    assert core.hidden_closed(category="software") == 0
    assert core.hidden_closed(query="satellite") == 1


def test_closed_always_after_open_whatever_the_sort():
    for sort, desc in [("ps_number", False), ("title", False), ("title", True), ("organization", True), ("relevance", False)]:
        got = core.search(query="telemetry parse portal drone", sort=sort, desc=desc, include_closed=True)[1]
        flags = [p.closed for p in got]
        assert flags == sorted(flags), (sort, desc)  # all False before any True
    assert nums(query="satellite telemetry")[1] == ["SIH1002"]  # closed still findable when included


def test_closed_outranked_by_open_even_if_more_relevant(monkeypatch):
    monkeypatch.setattr(core, "MIN_RELATIVE_SCORE", 0)  # this test is about ordering, not the weak-match cutoff
    # SIH1002 (closed) scores higher than SIH1003 (open) for this query, but must not precede it
    scores = core.Index([(p.title, f"{p.theme} {p.organization} {p.department} {p.ps_number}", p.description) for p in core.load()]).score("parser telemetry portal")
    by = {p.ps_number: sc for p, sc in zip(core.load(), scores)}
    assert by["SIH1002"] > by["SIH1003"] > 0
    got = nums(query="parser telemetry portal")[1]
    assert got.index("SIH1003") < got.index("SIH1002")


def test_get_finds_closed():
    assert core.get("SIH1002").closed
