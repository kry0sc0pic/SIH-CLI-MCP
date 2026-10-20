"""Ranked text search over problem statements: BM25 with light stemming, prefix/fuzzy/synonym expansion."""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import get_close_matches

K1, B = 1.5, 0.75
# field weights: a term in the title counts 3x, in theme/org/department/number 2x, in the description 1x
W_TITLE, W_META, W_DESC = 3, 2, 1
W_EXACT, W_PREFIX, W_FUZZY, W_SYN = 1.0, 0.8, 0.7, 0.6

STOP = frozenset("a an and are as at be by for from in is it of on or that the to with using use based via into over".split())

SYNONYMS = [
    {"farm", "farmer", "agricultur", "crop", "agri", "kisan", "irrigation", "soil"},
    {"ai", "ml", "llm", "neural", "intelligence"},
    {"drone", "uav", "uas", "quadcopter", "aerial"},
    {"cyber", "cybersecurity", "security", "malware", "threat", "encryption"},
    {"health", "healthcare", "medical", "medtech", "hospital", "patient", "diagnostic"},
    {"education", "school", "student", "teacher", "learning", "scholarship"},
    {"satellite", "space", "orbit", "isro", "remote"},
    {"blockchain", "ledger", "crypto", "cryptograph"},
    {"energy", "solar", "renewable", "power", "electricity", "grid"},
    {"traffic", "transport", "vehicle", "mobility", "logistic"},
    {"language", "nlp", "translation", "multilingual", "speech"},
    {"disaster", "flood", "cyclone", "earthquake", "landslide", "rescue"},
    {"water", "hydro", "river", "groundwater"},
    {"robot", "robotic", "automation", "automat"},
]

_SUFFIXES = ("ization", "isation", "ations", "ation", "ments", "ment", "ings", "ing", "ers", "er", "ed", "es", "ly", "al", "s")


def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    else:
        for suf in _SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def tokens(text: str) -> list[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def _syn_index() -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for group in SYNONYMS:
        stems = {stem(w) for w in group}
        for s in stems:
            idx.setdefault(s, set()).update(stems - {s})
    return idx


_SYN = _syn_index()


class Index:
    def __init__(self, docs: list[tuple[str, str, str]]):
        """docs: (title, meta, description) per document."""
        self.tf: list[Counter] = []
        self.len: list[float] = []
        df: Counter = Counter()
        for title, meta, desc in docs:
            c: Counter = Counter()
            for text, w in ((title, W_TITLE), (meta, W_META), (desc, W_DESC)):
                for t in tokens(text):
                    c[t] += w
            self.tf.append(c)
            self.len.append(sum(c.values()) or 1)
            df.update(c.keys())
        self.n = len(docs)
        self.df = df
        self.avg = sum(self.len) / max(self.n, 1)
        self.vocab = list(df)

    def idf(self, term: str) -> float:
        d = self.df.get(term, 0)
        return math.log(1 + (self.n - d + 0.5) / (d + 0.5))

    def variants(self, term: str, raw: str = "") -> dict[str, float]:
        """Vocabulary terms that can stand in for a query term (stem + the word as typed), with their weights."""
        out: dict[str, float] = {}
        if term in self.df:
            out[term] = W_EXACT
        if len(term) >= 4 or len(raw) >= 4:
            prefixes = {p for p in (term, raw) if len(p) >= 4}  # stemming can shorten "tele" to "tel"
            for v in self.vocab:
                if v != term and v.startswith(tuple(prefixes)):
                    out.setdefault(v, W_PREFIX)
            if term not in self.df and len(term) >= 4:
                for v in get_close_matches(term, self.vocab, n=3, cutoff=0.8):
                    out.setdefault(v, W_FUZZY)
        for s in _SYN.get(term, ()):
            if s in self.df:
                out.setdefault(s, W_SYN)
        return out

    def _bm25(self, doc: int, term: str) -> float:
        f = self.tf[doc].get(term, 0)
        if not f:
            return 0.0
        return self.idf(term) * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[doc] / self.avg))

    def score(self, query: str) -> list[float]:
        """Relevance per document; 0 means no match. Partial matches count, full matches rank higher."""
        pairs = {}
        for raw in re.findall(r"[a-z0-9]+", query.lower()):
            if raw not in STOP:
                pairs.setdefault(stem(raw), raw)
        qterms = list(pairs)
        if not qterms:
            return [0.0] * self.n
        variants = [self.variants(t, pairs[t]) for t in qterms]
        out = []
        for d in range(self.n):
            total, matched = 0.0, 0
            for vs in variants:
                best = max((w * self._bm25(d, v) for v, w in vs.items()), default=0.0)
                if best > 0:
                    matched += 1
                    total += best
            out.append(total * (matched / len(qterms)) ** 2 if matched else 0.0)
        return out
