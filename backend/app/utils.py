import re

_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def normalize_key(name: str) -> str:
    """Canonical entity key: lowercase, collapsed whitespace."""
    return re.sub(r"\s+", " ", name).strip().lower()


def lucene_escape(text: str) -> str:
    return _LUCENE_SPECIAL.sub(r"\\\1", text)


def clean_rel_type(rel: str) -> str:
    """'works on' -> 'WORKS_ON'."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", rel).strip("_").upper()
    return cleaned or "RELATED_TO"


def fuzzy_query(name: str) -> str:
    """Lucene query: boosted exact phrase OR fuzzy per-token match (typo tolerant)."""
    name = name.strip()
    tokens = [t for t in re.split(r"\s+", name) if len(t) > 1]
    parts = [f'"{lucene_escape(name)}"^4'] + [f"{lucene_escape(t)}~" for t in tokens]
    return " OR ".join(parts)
