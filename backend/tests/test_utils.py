from app.utils import clean_rel_type, fuzzy_query, lucene_escape, normalize_key


def test_normalize_key():
    assert normalize_key("  Maya   Patel ") == "maya patel"


def test_clean_rel_type():
    assert clean_rel_type("works on") == "WORKS_ON"
    assert clean_rel_type("???") == "RELATED_TO"


def test_lucene_escape():
    assert lucene_escape("R&D (EU)") == r"R\&D \(EU\)"


def test_fuzzy_query_contains_phrase_and_fuzzy_tokens():
    q = fuzzy_query("Maya Patel")
    assert '"Maya Patel"^4' in q and "Maya~" in q and "Patel~" in q
