"""Per-watchlist market vocabulary — the drift guard, for any business.

`in_market()` in the keyword engine stops a scan wandering into an adjacent market:
"espresso machine" must not drag it into "machine learning". That fence was built from
five hand-curated term lists, which covered the seeded demo verticals and nothing else.
A watchlist created from onboarding had no fence at all.

Three sources, in order: terms Claude wrote from the company's site, then terms derived
from the watchlist's own keywords, then nothing. All three feed the engine's existing
`vocabulary()` factory, so this is a wider source of terms rather than a new mechanism.
What never happens is borrowing another market's vocabulary.

Note this is a different thing from `watchlists.trends_category_id`, despite both being
called "the vertical". The category id scopes `cat=` on demand queries; these terms decide
whether a *keyword* belongs to the market. They answer different questions.
"""

from __future__ import annotations

import re
from typing import Any

from .coffee.engine import tokenize, vocabulary

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


def derive_terms(watchlist: Any) -> list[str]:
    """A vocabulary built from the watchlist's own keywords.

    Weaker than terms Claude wrote from the site, but never borrowed from another
    market: a mattress watchlist's keywords contain "mattress" and "foam", so they
    fence themselves. Reuses the engine's tokenize(), which already drops stopwords
    and short tokens — otherwise "best coffee online" would fence on "best", which
    matches everything and is the same as no fence.
    """
    terms: list[str] = []
    for kw in getattr(watchlist, "keywords", None) or []:
        for token in sorted(tokenize(getattr(kw, "term", ""))):
            if token not in terms:
                terms.append(token)
    return clean_terms(terms)


def for_watchlist(watchlist: Any) -> re.Pattern[str] | None:
    """The watchlist's market matcher, or None when there is nothing to build one from.

    Order matters: terms Claude wrote from the site beat terms derived from keywords,
    which beat nothing. What never happens is borrowing another market's vocabulary —
    filtering a mattress company's keywords through a coffee list would discard all of
    them, and silently.
    """
    terms = clean_terms(getattr(watchlist, "market_terms", None)) or derive_terms(watchlist)
    return vocabulary(terms) if terms else None
