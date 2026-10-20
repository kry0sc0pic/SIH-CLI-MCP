from sih.ranking import Index, stem, tokens

DOCS = [
    ("Smart farming assistant", "Agriculture SIH1", "Helps farmers detect crop disease early with images."),
    ("Flood prediction system", "Disaster SIH2", "Forecast urban flooding from rainfall data."),
    ("Satellite imagery change detection", "Space SIH3", "Compare multi-temporal satellite images."),
    ("Payments portal", "Finance SIH4", "A portal for security deposits."),
]


def ranked(q):
    idx = Index(DOCS)
    s = idx.score(q)
    return [i for i in sorted(range(len(DOCS)), key=lambda i: -s[i]) if s[i] > 0]


def test_stemming_is_consistent():
    assert stem("farming") == stem("farmers") == stem("farm") == "farm"
    assert stem("agriculture") == stem("agricultural")
    assert stem("drones") == stem("drone")
    assert stem("cities") == "city" and stem("ai") == "ai"
    assert tokens("The Drones, and the AI!") == ["dron", "ai"]


def test_exact_prefix_typo_synonym():
    assert ranked("farming")[0] == 0
    assert ranked("agri")[0] == 0  # prefix
    assert ranked("satelite")[0] == 2  # typo
    assert ranked("kisan")[0] == 0  # synonym of farm
    assert ranked("cyclone")[0] == 1  # same synonym group as flood
    assert ranked("zzzzqqq") == []


def test_title_beats_description():
    assert ranked("portal")[0] == 3
    # "images" appears in a description only, "imagery" in a title
    assert ranked("imagery")[0] == 2


def test_all_terms_beat_partial():
    r = ranked("satellite flood")
    assert set(r[:2]) == {1, 2}
    r = ranked("farming disease")
    assert r[0] == 0


def test_empty_and_stopword_queries():
    assert ranked("") == [] and ranked("the of and") == []
