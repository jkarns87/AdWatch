"""Google Trends categories — the closed set Claude classifies into.

The point of classifying rather than generating is that the answer is checkable:
an id either exists in this enumeration or it does not. Everything else about the
vertical rests on that.
"""

import pytest

from app import taxonomy


def test_the_taxonomy_loads_and_is_not_truncated():
    assert len(taxonomy.all_categories()) > 1000


def test_known_nodes_are_present():
    assert taxonomy.name_for(0) == "All categories"
    assert taxonomy.name_for(71) == "Food & Drink"
    assert taxonomy.name_for(7) == "Finance"


def test_an_unknown_id_is_rejected():
    """A hallucinated id must not reach cat= on a trends query."""
    assert taxonomy.is_valid(71) is True
    assert taxonomy.is_valid(999999) is False
    assert taxonomy.name_for(999999) is None


def test_ids_are_unique():
    ids = [c["id"] for c in taxonomy.all_categories()]
    assert len(ids) == len(set(ids))


def test_search_finds_by_substring_case_insensitively():
    """Backs the typeahead, and lets a test assert a subtree without hardcoding ids."""
    hits = {c["id"] for c in taxonomy.search("coffee")}
    assert hits, "expected at least one coffee-ish category"
    assert all("coffee" in taxonomy.name_for(i).lower() for i in hits)


def test_search_is_bounded():
    assert len(taxonomy.search("a", limit=5)) <= 5


def test_coercing_a_model_answer_accepts_a_valid_id(caplog):
    assert taxonomy.coerce(71) == 71


@pytest.mark.parametrize("bad", [None, "", "seventy-one", 999999, -1, 3.5])
def test_coercing_rejects_anything_not_in_the_set(bad):
    """Claude returns JSON; a string id, a null, or an invented number must all land
    on None rather than being written to the watchlist."""
    assert taxonomy.coerce(bad) is None


def test_a_numeric_string_is_accepted_since_json_typing_is_loose():
    assert taxonomy.coerce("71") == 71
