"""Per-watchlist market vocabulary — the drift guard, for any business.

`in_market()` in the keyword engine stops a scan wandering into an adjacent market:
"espresso machine" must not drag it into "machine learning". That fence was built from
five hand-curated term lists, which covered the seeded demo verticals and nothing else.
A watchlist created from onboarding had no fence at all.

Claude already reads the company's site during onboarding, so it supplies the terms, and
the engine's existing `vocabulary()` factory turns them into the same kind of matcher the
curated lists produce. No new mechanism — just a wider source of terms.

Note this is a different thing from `watchlists.trends_category_id`, despite both being
called "the vertical". The category id scopes `cat=` on demand queries; these terms decide
whether a *keyword* belongs to the market. They answer different questions.
"""

from __future__ import annotations

import re
from typing import Any

from .coffee.engine import vocabulary

MAX_TERMS = 80
MIN_TERM_LENGTH = 2


def clean_terms(value: Any) -> list[str]:
    """Keep the usable strings. Single characters are dropped — a one-letter term
    matches almost everything and would turn the fence into a no-op."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for t in value:
        if not isinstance(t, str):
            continue
        term = t.strip().lower()
        if len(term) >= MIN_TERM_LENGTH and term not in out:
            out.append(term)
    return out[:MAX_TERMS]


def for_watchlist(watchlist: Any) -> re.Pattern[str] | None:
    """The watchlist's market matcher, or None when it has no terms.

    None means "do not filter", never "fall back to coffee" — filtering a mattress
    company's keywords through a coffee vocabulary would discard all of them.
    """
    terms = clean_terms(getattr(watchlist, "market_terms", None))
    return vocabulary(terms) if terms else None
