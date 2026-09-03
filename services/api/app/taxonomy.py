"""Google Trends category taxonomy — the closed set the vertical is classified into.

Classifying into a published enumeration rather than generating a string is what makes
the model's answer checkable: an id either exists here or it does not, and a valid id
feeds straight into `cat=` on every trends query for the watchlist.

The data is a committed asset (`data/trends_categories.json`) rather than a runtime
fetch: no network dependency at import, and the file records when it was captured.
Regenerate it when Google changes the tree.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("data") / "trends_categories.json"


@lru_cache(maxsize=1)
def _loaded() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text())


@lru_cache(maxsize=1)
def _by_id() -> dict[int, str]:
    return {c["id"]: c["name"] for c in _loaded()["categories"]}


def all_categories() -> list[dict[str, Any]]:
    return _loaded()["categories"]


def fetched_on() -> str:
    """When the asset was captured, so staleness is visible rather than assumed."""
    return _loaded().get("fetched", "unknown")


def is_valid(category_id: int) -> bool:
    return category_id in _by_id()


def name_for(category_id: int) -> str | None:
    return _by_id().get(category_id)


def search(term: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Substring match, for the typeahead. Bounded so a one-letter query is cheap."""
    needle = (term or "").strip().lower()
    if not needle:
        return []
    return [c for c in all_categories() if needle in c["name"].lower()][:limit]


def coerce(value: Any) -> int | None:
    """Turn a model's answer into a valid category id, or None.

    Claude returns JSON, so the id may arrive as a string. Anything that is not an
    integer present in the taxonomy — a name, a null, an invented number — returns None
    rather than being written to the watchlist.
    """
    if isinstance(value, bool):  # bool is an int subclass; not a category id
        return None
    if isinstance(value, int):
        return value if is_valid(value) else None
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        as_int = int(value.strip())
        return as_int if is_valid(as_int) else None
    return None
