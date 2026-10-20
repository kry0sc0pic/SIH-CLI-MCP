"""Fetch, parse, cache and query SIH problem statements."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

from .ranking import Index

URL = os.environ.get("SIH_URL", "https://www.sih.gov.in/sih2026PS")
CACHE_DIR = Path(os.environ.get("SIH_CACHE_DIR", Path.home() / ".cache" / "sih"))
CACHE_FILE = CACHE_DIR / "problem_statements.json"
CACHE_TTL = 6 * 3600
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"

MIN_RELATIVE_SCORE = 0.15
SORT_KEYS = ("relevance", "ps_number", "title", "organization", "category", "theme", "ideas", "deadline")


@dataclass
class PS:
    ps_number: str
    ps_id: str
    title: str
    organization: str
    department: str
    category: str
    theme: str
    ideas: int | None  # None when submissions are closed (the site hides the count)
    ideas_cap: int | None
    closed: bool
    deadline: str | None  # ISO date
    description: str
    youtube: str = ""
    dataset_links: list[str] = field(default_factory=list)
    contact: str = ""

    def summary(self, snippet: int = 240) -> dict:
        d = asdict(self)
        d["description"] = _snippet(self.description, snippet)
        return d


def _snippet(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", s)).strip()


def _date(s: str) -> str | None:
    for fmt in ("%d %B %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse(html: str) -> list[PS]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="dataTablePS")
    if not table:
        raise RuntimeError("problem statement table not found; page layout may have changed")
    out = []
    for tr in table.tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue
        modal = tds[2].find("div", class_="modal-body")
        fields: dict[str, Tag] = {}
        if modal:
            for row in modal.find_all("tr"):
                th, td = row.find("th"), row.find("td")
                if th and td:
                    fields[th.get_text(strip=True)] = td
        txt = lambda k: _clean(fields[k].get_text("\n")) if k in fields else ""
        count_text = tds[5].get_text()
        count = re.match(r"\s*(\d+)\s*(?:/\s*(\d+))?", count_text)
        closed = "closed" in count_text.lower()
        links = [a["href"].strip() for a in fields.get("Dataset Link", Tag(name="x")).find_all("a", href=True) if a["href"].strip()]
        yt = [a["href"].strip() for a in fields.get("Youtube Link", Tag(name="x")).find_all("a", href=True) if a["href"].strip()]
        out.append(
            PS(
                ps_number=tds[4].get_text(strip=True),
                ps_id=txt("Problem Statement ID"),
                title=txt("Problem Statement Title") or tds[2].a.get_text(strip=True),
                organization=tds[1].get_text(strip=True),
                department=txt("Department"),
                category=tds[3].get_text(strip=True).capitalize(),
                theme=tds[6].get_text(strip=True),
                ideas=int(count.group(1)) if count else None,
                ideas_cap=int(count.group(2)) if count and count.group(2) else None,
                closed=closed,
                deadline=_date(tds[7].get_text()),
                description=txt("Description"),
                youtube=yt[0] if yt else "",
                dataset_links=links,
                contact=txt("Contact info"),
            )
        )
    return out


def refresh() -> list[PS]:
    r = httpx.get(URL, headers={"User-Agent": UA}, timeout=60, follow_redirects=True)
    r.raise_for_status()
    items = parse(r.text)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"fetched_at": time.time(), "url": URL, "items": [asdict(i) for i in items]}))
    return items


def load(force: bool = False) -> list[PS]:
    if not force and CACHE_FILE.exists():
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data["fetched_at"] < CACHE_TTL and all("closed" in i for i in data["items"][:1]):
            return [PS(**i) for i in data["items"]]
    return refresh()


def cache_info() -> dict:
    if not CACHE_FILE.exists():
        return {"cached": False}
    d = json.loads(CACHE_FILE.read_text())
    return {"cached": True, "count": len(d["items"]), "fetched_at": datetime.fromtimestamp(d["fetched_at"]).isoformat(timespec="seconds"), "path": str(CACHE_FILE)}


def _eq(a: str, b: str | None) -> bool:
    return b is None or b.strip().lower() in a.lower()


def search(
    query: str | None = None,
    organization: str | None = None,
    category: str | None = None,
    theme: str | None = None,
    department: str | None = None,
    max_ideas: int | None = None,
    min_ideas: int | None = None,
    open_only: bool = False,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    sort: str | None = None,
    desc: bool = False,
    limit: int = 20,
    offset: int = 0,
    force: bool = False,
    include_closed: bool = False,
) -> tuple[int, list[PS]]:
    """Filter, rank and sort. Returns (total, page).

    `query` is ranked (BM25 over title/theme/org/description with stemming, prefix, typo and synonym matching);
    statements matching only some terms are kept but rank lower. sort defaults to relevance when there is a query,
    else ps_number. Closed statements are hidden unless include_closed, and always come after open ones.
    """
    sort = sort or ("relevance" if query else "ps_number")
    if sort not in SORT_KEYS:
        raise ValueError(f"sort must be one of {SORT_KEYS}")
    today = datetime.now().date().isoformat()
    everything = load(force)
    scores = Index([(p.title, f"{p.theme} {p.organization} {p.department} {p.ps_number}", p.description) for p in everything]).score(query) if query else None
    scored: list[tuple[float, PS]] = []
    for i, p in enumerate(everything):
        if p.closed and not include_closed:
            continue
        if not (_eq(p.organization, organization) and _eq(p.category, category) and _eq(p.theme, theme) and _eq(p.department, department)):
            continue
        if max_ideas is not None and (p.ideas is None or p.ideas > max_ideas):
            continue
        if min_ideas is not None and (p.ideas is None or p.ideas < min_ideas):
            continue
        if open_only and (p.deadline or "9999") < today:
            continue
        if deadline_from and (p.deadline or "") < deadline_from:
            continue
        if deadline_to and (p.deadline or "9999") > deadline_to:
            continue
        if scores is not None and scores[i] <= 0:
            continue
        scored.append((scores[i] if scores else 0.0, p))
    if scored and scores is not None:  # drop weak partial matches next to strong ones among what is being shown
        cutoff = MIN_RELATIVE_SCORE * max(sc for sc, _ in scored)
        scored = [(sc, p) for sc, p in scored if sc >= cutoff]
    key = {
        "ideas": lambda p: p.ideas or 0,
        "deadline": lambda p: p.deadline or "9999",
        "ps_number": lambda p: (len(p.ps_number), p.ps_number),
    }.get(sort, lambda p: getattr(p, sort).lower())
    if sort == "relevance":
        scored.sort(key=lambda sp: sp[0], reverse=not desc)
    else:
        scored.sort(key=lambda sp: key(sp[1]), reverse=desc)
    items = [p for _, p in scored]
    items = [p for p in items if not p.closed] + [p for p in items if p.closed]  # open first, whatever the sort
    return len(items), items[offset : offset + limit]


def hidden_closed(**filters) -> int:
    """How many closed statements a search with these filters leaves out by default."""
    filters.pop("include_closed", None)
    return search(include_closed=True, limit=0, **filters)[0] - search(limit=0, **filters)[0]


def get(ref: str) -> PS | None:
    ref = ref.strip().upper().removeprefix("SIH")
    return next((p for p in load() if p.ps_number.upper().removeprefix("SIH") == ref or p.ps_id == ref), None)


def facets(include_closed: bool = False) -> dict:
    from collections import Counter

    everything = load()
    items = [p for p in everything if include_closed or not p.closed]
    return {
        "total": len(items),
        "closed_hidden": len(everything) - len(items),
        "organization": Counter(p.organization for p in items).most_common(),
        "category": Counter(p.category for p in items).most_common(),
        "theme": Counter(p.theme for p in items).most_common(),
    }
