"""Top coffee keywords for a seed term, read out of the live paid block.

Google does not publish which keywords an advertiser targets, so "what should we
bid on for `coffee nearby`?" normally gets answered with estimated search
volume - a number about searchers, not about competitors. This answers it from
the sponsored results themselves:

    seed -> expansion (autocomplete + a commercial ladder)
         -> paid block for each query (SerpApi `google`, in parallel)
         -> keywords recovered from the ads
         -> ranked by how many advertisers are observably competing on them

Three signals come out of an ad block, strongest first:

  targeting_keyword  Google expands the ValueTrack macros {keyword} and
                     {matchtype} into the click URL, and advertisers who
                     forward them to their landing page (utm_term / hsa_kw /
                     keyword, usually inside the percent-encoded adurl= of the
                     aclk link) name the exact term and match type they target.
  sponsored_query    an advertiser was served against the query we searched.
  ad_copy            a phrase two or more advertisers write in their copy.

plus `autocomplete`, which is a suggestion with no advertiser behind it.

Every score is reproducible: the response returns the formula and weights it
used, so any row can be recomputed by hand from its `signals`. Nothing about
bids, budgets, spend or impression share is inferred - SerpApi does not return
it, and `ads_exposing_a_keyword` states how much of the block was readable.

Scoped to coffee (see `COFFEE_TERMS`): an off-market seed is rejected before any
search is spent, and expansions and recovered keywords are filtered back to the
market so a scan cannot wander into an adjacent one.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ..collectors.normalize import domain_of
from ..collectors.serpapi_client import SerpApiClient, SerpApiError

log = logging.getLogger(__name__)

# SerpApiClient raises SerpApiError(f"SerpApi {status}: ...") and keeps no status attribute.
# Reading it back off the message keeps this feature from having to change the client.
_STATUS = re.compile(r"^SerpApi (\d{3})\b")


def upstream_status(e: SerpApiError) -> int | None:
    """The HTTP status behind a SerpApiError, or None if it never left the process."""
    m = _STATUS.match(str(e))
    return int(m.group(1)) if m else None

# `engine=google_ads` rejects a request with no `location` (400 "Missing `location` parameter"),
# and ads are local anyway, so a scan always names a market.
DEFAULT_LOCATION = "United States"
MAX_DEPTH = 6
MAX_LIMIT = 100
ESCALATION_QUERIES = 3   # extra scans when nobody advertises on the seed
ESCALATION_FLOOR = 3     # ...meaning fewer advertisers than this

# ---- scope ---------------------------------------------------------------------------------

# Drinks, preparations, equipment and trade terms. Matched on word boundaries, so
# "brewery" is not "brew". Retargeting this service at another vertical is an edit here.
COFFEE_TERMS = [
    "coffee", "coffees", "cafe", "cafes", "café", "cafés", "coffeehouse", "coffeehouses",
    "coffee shop", "coffee shops", "caffeine", "decaf", "decaffeinated",
    "espresso", "espressos", "latte", "lattes", "cappuccino", "cappuccinos", "americano",
    "macchiato", "mocha", "mochas", "cortado", "flat white", "affogato", "ristretto",
    "doppio", "frappuccino", "frappe", "frappé", "cold brew", "nitro brew",
    "arabica", "robusta", "roaster", "roasters", "roastery", "roasteries", "roast",
    "roasts", "roasted", "single origin", "whole bean", "whole beans",
    "barista", "baristas", "brew", "brews", "brewed", "brewer", "brewers",
    "french press", "pour over", "pourover", "aeropress", "chemex", "moka pot", "percolator",
    "k-cup", "k cup", "k-cups", "k cups", "keurig", "nespresso", "coffee pod", "coffee pods",
    "instant coffee",
]
COFFEE = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(COFFEE_TERMS, key=len, reverse=True)) + r")\b")

OFF_MARKET_MESSAGE = (
    "This endpoint covers coffee-related searches only. Try keywords such as 'coffee nearby', "
    "'coffee subscription', 'espresso machine' or 'cold brew delivery'."
)


def is_coffee(text: str | None) -> bool:
    """True when a query or keyword belongs to the coffee market."""
    return bool(COFFEE.search((text or "").lower()))


# ---- expansion -----------------------------------------------------------------------------

# Modifiers that make a query local or informational rather than commercial. "coffee nearby" is
# a map query - nobody buys clicks on it - but the market behind it is real, and it is reached
# by stripping back to the head term.
LOCAL_MODIFIERS = re.compile(
    r"\b(nearby|near me|near by|around me|close by|closest|in my area|open now|open today|hours|menu|directions|map)\b"
)
INFO_PREFIX = re.compile(r"^(what|which|who|why|when|how|is|are|does|the|a|an)\s+")

# Generic commercial ladder, most broadly applicable first, applied to the head term.
COMMERCIAL_TEMPLATES = ["best {q}", "{q} price", "buy {q} online", "{q} deals", "{q} subscription", "{q} delivery", "cheap {q}"]

# Promotes autocomplete suggestions that already carry buying intent.
COMMERCIAL_WORDS = re.compile(
    r"\b(buy|price|pricing|cost|cheap|deal|deals|discount|coupon|sale|order|delivery|deliver|subscription|"
    r"subscribe|shop|store|service|company|best|top|online|quote|plans?)\b"
)

STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "your", "you", "our", "we", "us", "to", "of", "in", "on", "at", "by",
    "from", "get", "now", "today", "up", "all", "new", "is", "are", "it", "its", "or", "no", "as", "that", "this",
    "more", "most", "over", "only", "just", "shop", "save", "off", "free", "best", "top", "buy", "online",
    "official", "site", "than", "when", "why", "how", "what", "who", "every", "any", "into", "out",
}
# Stopwords a real keyword can contain in the middle ("coffee for office"). Any other stopword
# inside an n-gram means the window ran across a sentence, not a phrase.
INNER_OK = {"for", "near", "at", "in", "to", "with", "of", "on", "by", "per"}
WORD = re.compile(r"[a-z0-9][a-z0-9'&+-]*")


def tokenize(text: str | None) -> set[str]:
    return {w for w in WORD.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 2}


def head_term(seed: str) -> str:
    """The seed stripped back to what is actually being shopped for."""
    h = seed.lower().strip()
    while INFO_PREFIX.match(h):
        h = INFO_PREFIX.sub("", h, count=1)
    h = LOCAL_MODIFIERS.sub(" ", h)
    h = re.sub(r"\s+", " ", h).strip(" -,")
    return h or seed.lower().strip()


def commercial_ladder(head: str) -> list[str]:
    """Commercial variants of the head term, skipping words it already uses."""
    words = set(head.split())
    return [t.format(q=head) for t in COMMERCIAL_TEMPLATES if not {w for w in t.replace("{q}", " ").split() if w} & words]


def _interleave(a: list[str], b: list[str]) -> list[str]:
    """Alternate two ranked lists, keeping the head of each near the front."""
    out: list[str] = []
    for pair in zip(a, b, strict=False):
        out += list(pair)
    return out + a[len(b):] + b[len(a):]


def autocomplete_index(suggestions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Suggestions keyed by query, with their relevance relative to the top one.

    SerpApi returns `relevance` per suggestion; it orders one response and is
    not a search volume, so it is reported as a share and weighted lowest.
    """
    top = max((s.get("relevance") or 0 for s in suggestions), default=0)
    out: dict[str, dict[str, Any]] = {}
    for rank, s in enumerate(suggestions, 1):
        q = (s.get("value") or "").strip().lower()
        if not q or q in out:
            continue
        out[q] = {"rank": rank, "relevance": s.get("relevance"), "share": round((s.get("relevance") or 0) / top, 3) if top else 0.0}
    return out


def plan_queries(client: SerpApiClient, seed: str, depth: int, *, gl: str = "us", fresh: bool = False) -> tuple[list[str], dict, list[str]]:
    """(queries to scan, autocomplete index, unspent commercial queries).

    The reserve is kept for escalation: if the seed turns out to have no
    advertisers, it is cheaper to spend a few more searches on the commercial
    terms behind it than to return suggestion noise.
    """
    seed = seed.lower().strip()
    seed_tokens = tokenize(seed)
    head = head_term(seed)
    if not is_coffee(head):
        head = seed   # stripping went too far; keep the market in view

    try:
        suggestions = (client.search({"engine": "google_autocomplete", "q": seed, "gl": gl, "hl": "en"}, fresh=fresh).data.get("suggestions")) or []
    except SerpApiError as e:
        if upstream_status(e) in (401, 403, 429):
            raise
        log.warning("autocomplete failed, continuing with the ladder only: %s", e)
        suggestions = []
    demand = autocomplete_index(suggestions)

    # Stay on topic and inside the market: "espresso machine" must not drag the scan into
    # "machine learning", and this endpoint only covers coffee.
    on_topic = sorted(
        (q for q in demand if q != seed and (tokenize(q) & seed_tokens) and is_coffee(q)),
        key=lambda q: -(demand[q]["relevance"] or 0),
    )
    ladder = commercial_ladder(head)

    picks, seen = [], {seed}
    for q in _interleave([q for q in on_topic if COMMERCIAL_WORDS.search(q)], ladder) + on_topic:
        if len(picks) >= depth:
            break
        if q not in seen:
            seen.add(q)
            picks.append(q)
    return [seed] + picks, demand, [q for q in ladder if q not in seen]


# ---- recovery ------------------------------------------------------------------------------

KEYWORD_PARAMS = ("utm_term", "hsa_kw", "keyword", "searchterm", "kw")
MATCH_PARAMS = ("matchtype", "hsa_mt", "mt")
MATCH_NAMES = {"b": "broad", "p": "phrase", "e": "exact"}
EMBEDDED_KEYWORD = re.compile(r"keyword[-_]([a-z0-9 %+]{3,40})", re.I)
EMBEDDED_MATCH = re.compile(r"matchtype[-_]([bpe])(?![a-z])", re.I)
JUNK = re.compile(r"^(kwd-\d+|\{.*|[\d_\-.]+)$", re.I)   # Google IDs and macros Google never expanded
COPY_NOISE = re.compile(
    r"\b(learn more|sign up|free shipping|order now|shop now|click here|limited time|money back|customer service)\b", re.I
)
MAX_REDIRECT_DEPTH = 3


def _walk_params(url: str | None, depth: int = 0):
    """Query params from a URL and from any URL nested inside it.

    An ad click is a redirect chain: the landing URL carrying utm_term is
    usually a percent-encoded parameter of the Google click URL.
    """
    if not url or depth > MAX_REDIRECT_DEPTH:
        return
    try:
        qs = parse_qs(urlparse(url).query)
    except ValueError:
        return
    yield qs
    for values in qs.values():
        for v in values:
            if v.startswith("http") or "utm_" in v or "hsa_" in v:
                yield from _walk_params(v, depth + 1)


def clean_keyword(value: str) -> str | None:
    """Normalise one candidate keyword, or None if it isn't one."""
    v = unquote(value).replace("+", " ").strip().lower()
    embedded = EMBEDDED_KEYWORD.search(v)
    if embedded:
        v = unquote(embedded.group(1)).replace("+", " ").strip()
    v = re.sub(r"\s+", " ", v)
    if len(v) < 3 or len(v) > 60 or JUNK.match(v):
        return None
    if "_" in v and len(v) > 45 and not embedded:   # a tracking payload, not a keyword
        return None
    return v


def targeting_from_ad(ad: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(keywords, match_types) recovered from one raw `ads[]` entry."""
    keywords: set[str] = set()
    matches: set[str] = set()
    for url in (ad.get("tracking_link"), ad.get("link")):
        for qs in _walk_params(url):
            for key in KEYWORD_PARAMS:
                for raw in qs.get(key, []):
                    kw = clean_keyword(raw)
                    if kw:
                        keywords.add(kw)
            for key in MATCH_PARAMS:
                for raw in qs.get(key, []):
                    if len(raw) <= 6 and raw[:1].lower() in MATCH_NAMES:
                        matches.add(MATCH_NAMES[raw[0].lower()])
            for raw in (v for vs in qs.values() for v in vs):
                m = EMBEDDED_MATCH.search(raw)
                if m:
                    matches.add(MATCH_NAMES[m.group(1).lower()])
    return sorted(keywords), sorted(matches)


def advertiser_of(ad: dict[str, Any]) -> str:
    """Landing domain, same value `normalize.serp_ads_from_google` stores.

    Falls back to the `adurl` inside the tracking link when the displayed link
    is missing or is Google's own redirector, so an advertiser is never lost.
    """
    domain = domain_of(ad.get("displayed_link") or ad.get("link"))
    if domain and domain != "google.com":
        return domain
    for field in ("tracking_link", "link"):
        for qs in _walk_params(ad.get(field)):
            for key in ("adurl", "url", "q"):
                for raw in qs.get(key, []):
                    d = domain_of(unquote(raw))
                    if d and d != "google.com":
                        return d
    return domain


def copy_phrases(ad: dict[str, Any], seed_tokens: set[str], max_words: int = 4) -> set[str]:
    """Candidate phrases from ad copy, kept only when they touch the seed vocabulary.

    An ad for a coffee subscription also says "money back guarantee" - real copy,
    but not a keyword anyone in this market is targeting.
    """
    parts = [ad.get("title"), ad.get("description")]
    for sl in ad.get("sitelinks") or []:
        parts += [sl.get("title"), sl.get("description")]
    text = COPY_NOISE.sub(" ", " . ".join(p for p in parts if p).lower())

    out: set[str] = set()
    for sentence in re.split(r"[.!?|·—–\-\n,;:()\"]+", text):
        words = WORD.findall(sentence)
        for n in range(2, max_words + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                    continue
                if any(w in STOPWORDS and w not in INNER_OK for w in gram[1:-1]):
                    continue
                if any("'" in w or len(w) < 2 for w in gram):
                    continue
                phrase = " ".join(gram)
                if 5 <= len(phrase) <= 60 and seed_tokens & set(gram):
                    out.add(phrase)
    return out


# ---- scan ----------------------------------------------------------------------------------


def _ads_for(client: SerpApiClient, query: str, location: str | None, gl: str, fresh: bool) -> tuple[list[dict], list[str]]:
    """The paid block for one query, plus Google's own related searches."""
    params = {"engine": "google_ads", "q": query, "gl": gl, "hl": "en", "device": "desktop", "google_domain": "google.com", "location": location}
    data = client.search(params, fresh=fresh).data
    ads = []
    for i, ad in enumerate(data.get("ads") or []):
        domain = advertiser_of(ad)
        if not domain or domain == "google.com":
            continue
        keywords, matches = targeting_from_ad(ad)
        ads.append(
            {
                "query": query,
                "advertiser_domain": domain,
                "position": int(ad.get("position") or i + 1),
                "title": ad.get("title") or "",
                "description": ad.get("description"),
                "displayed_link": ad.get("displayed_link"),
                "targeting_keywords": keywords,
                "match_types": matches,
                "raw": ad,
            }
        )
    related = [(r.get("query") or "").strip().lower() for r in data.get("related_searches") or []]
    return ads, [r for r in related if r]


def _scan(client: SerpApiClient, queries: list[str], location: str | None, gl: str, fresh: bool) -> tuple[list[dict], set[str], list[dict]]:
    """Several queries at once. Wall clock here is almost all SerpApi latency.

    One query failing is survivable and comes back as a warning; a key or quota
    failure is not, and propagates so the caller can return 401/429.
    """
    ads: list[dict] = []
    related: set[str] = set()
    warnings: list[dict] = []
    if not queries:
        return ads, related, warnings
    with ThreadPoolExecutor(max_workers=min(5, len(queries))) as pool:
        futures = {pool.submit(_ads_for, client, q, location, gl, fresh): q for q in queries}
        for fut, q in futures.items():
            try:
                got, rel = fut.result()
            except SerpApiError as e:
                if upstream_status(e) in (401, 403, 429):
                    raise
                warnings.append({"query": q, "error": str(e)})
                continue
            ads += got
            related |= set(rel)
    return ads, related, warnings


# ---- scoring -------------------------------------------------------------------------------

# What each signal is worth per distinct advertiser behind it. A term read out of an
# advertiser's own tracking URL is that advertiser naming its target; a term in ad copy is only
# a hint that they wrote about it; a suggestion with no advertiser is the weakest thing here.
W_TARGETING = 6.0
W_SPONSORED_QUERY = 3.0
W_COPY = 1.5
W_AUTOCOMPLETE = 2.0     # scaled by relevance share, 0..1
W_RELATED = 1.0
SCORE_REFERENCE = 30.0   # raw score that maps to 100: five advertisers naming the keyword

# An autocomplete-only row has no advertiser behind it and would otherwise fill a thin table.
AUTOCOMPLETE_ONLY_SHARE = 0.34

# Bucketed advertiser counts seen in this scan. Not Google Keyword Planner's "competition"
# metric - SerpApi's `google` engine does not return that.
BANDS = ((6, "high"), (3, "medium"), (1, "low"))

SCORING = {
    "formula": (
        "score = 100 * min(1, (6*targeting_keyword_advertisers + 3*sponsored_query_advertisers "
        "+ 1.5*ad_copy_advertisers + 2*autocomplete_relevance_share + 1*related_search) / 30)"
    ),
    "weights": {
        "targeting_keyword_advertisers": W_TARGETING,
        "sponsored_query_advertisers": W_SPONSORED_QUERY,
        "ad_copy_advertisers": W_COPY,
        "autocomplete_relevance_share": W_AUTOCOMPLETE,
        "related_search": W_RELATED,
    },
    "reference": SCORE_REFERENCE,
    "competition_bands": {"high": ">= 6 advertisers", "medium": "3-5 advertisers", "low": "1-2 advertisers", "none": "0 advertisers"},
}


def band(advertiser_count: int) -> str:
    for floor, name in BANDS:
        if advertiser_count >= floor:
            return name
    return "none"


def _blank() -> dict[str, Any]:
    return {
        "targeting_advertisers": set(),
        "query_advertisers": set(),
        "copy_advertisers": set(),
        "match_types": set(),
        "queries": set(),
        "ads": 0,
        "autocomplete": None,
        "related_search": False,
        "example": None,
    }


def _score_row(keyword: str, c: dict[str, Any]) -> dict[str, Any]:
    tgt, qadv, copy = len(c["targeting_advertisers"]), len(c["query_advertisers"]), len(c["copy_advertisers"])
    share = (c["autocomplete"] or {}).get("share") or 0.0
    raw = W_TARGETING * tgt + W_SPONSORED_QUERY * qadv + W_COPY * copy + W_AUTOCOMPLETE * share + (W_RELATED if c["related_search"] else 0)
    advertisers = c["targeting_advertisers"] | c["query_advertisers"] | c["copy_advertisers"]
    ex = c["example"]
    return {
        "keyword": keyword,
        "score": round(min(100.0, 100 * raw / SCORE_REFERENCE), 1),
        "raw": raw,
        "recovered_from_ad": tgt > 0,
        "evidence": "targeting_keyword" if tgt else "sponsored_query" if qadv else "ad_copy" if copy else "autocomplete",
        "advertiser_count": len(advertisers),
        "advertisers": sorted(advertisers)[:12],
        "competition": band(len(advertisers)),
        "match_types": sorted(c["match_types"]),
        "ads": c["ads"],
        "signals": {
            "targeting_keyword_advertisers": tgt,
            "sponsored_query_advertisers": qadv,
            "ad_copy_advertisers": copy,
            "autocomplete_rank": (c["autocomplete"] or {}).get("rank"),
            "autocomplete_relevance_share": share or None,
            "related_search": c["related_search"],
        },
        "seen_on_queries": sorted(c["queries"])[:8],
        "example_ad": {
            "advertiser_domain": ex["advertiser_domain"],
            "title": ex["title"],
            "description": ex["description"],
            "displayed_link": ex["displayed_link"],
        }
        if ex
        else None,
    }


def _uncorroborated_copy(row: dict[str, Any]) -> bool:
    """A phrase one advertiser wrote that nothing else corroborates.

    Ad copy is prose, so a sliding window over it produces real keywords next to
    sentence fragments. A keyword recurs across advertisers or shows up in search
    suggestions; a fragment does neither.
    """
    sig = row["signals"]
    return row["evidence"] == "ad_copy" and sig["ad_copy_advertisers"] < 2 and not sig["autocomplete_rank"] and not sig["related_search"]


def _cap_autocomplete_only(rows: list[dict], limit: int) -> list[dict]:
    """Keep the table mostly about keywords that have advertisers behind them."""
    budget = max(3, int(limit * AUTOCOMPLETE_ONLY_SHARE))
    out, spent = [], 0
    for r in rows:
        if r["evidence"] == "autocomplete":
            if spent >= budget:
                continue
            spent += 1
        out.append(r)
    return out


def rank(ads: list[dict], *, seed: str, demand: dict, related: set[str], limit: int) -> list[dict]:
    """Turn scanned ads plus suggestion signals into the ranked keyword table."""
    seed_tokens = tokenize(seed)
    cand: dict[str, dict[str, Any]] = {}

    def rec(kw: str) -> dict[str, Any]:
        return cand.setdefault(kw, _blank())

    per_query: dict[str, set[str]] = {}
    for ad in ads:
        domain, q = ad["advertiser_domain"], ad["query"]
        per_query.setdefault(q, set()).add(domain)
        for kw in ad["targeting_keywords"]:
            c = rec(kw)
            c["targeting_advertisers"].add(domain)
            c["match_types"].update(ad["match_types"])
            c["queries"].add(q)
            c["ads"] += 1
            c["example"] = c["example"] or ad
        for phrase in copy_phrases(ad["raw"], seed_tokens):
            c = rec(phrase)
            c["copy_advertisers"].add(domain)
            c["queries"].add(q)
            c["example"] = c["example"] or ad

    # A query we scanned: an advertiser shown on it is targeting it by definition, so the
    # advertiser count on a query is a competition reading for that query.
    for q, domains in per_query.items():
        c = rec(q)
        c["query_advertisers"] |= domains
        c["queries"].add(q)
        c["ads"] += sum(1 for a in ads if a["query"] == q)

    for kw, c in cand.items():
        c["autocomplete"] = demand.get(kw)
        c["related_search"] = kw in related
    for kw in (related | set(demand)) - set(cand):
        if not (tokenize(kw) & seed_tokens) or not is_coffee(kw):
            continue
        c = rec(kw)
        c["autocomplete"] = demand.get(kw)
        c["related_search"] = kw in related

    rows = [_score_row(kw, c) for kw, c in cand.items()]
    rows = [r for r in rows if r.pop("raw") > 0 and not _uncorroborated_copy(r) and is_coffee(r["keyword"])]
    rows.sort(key=lambda r: (-r["score"], -r["advertiser_count"], r["keyword"]))
    return _cap_autocomplete_only(rows, limit)


# ---- entry point ---------------------------------------------------------------------------


def discover(
    client: SerpApiClient,
    seed: str,
    *,
    location: str | None = None,
    gl: str = "us",
    depth: int = 4,
    limit: int = 25,
    fresh: bool = False,
) -> dict[str, Any]:
    """Scan the paid block around `seed` and return the ranked coffee keywords.

    Costs 1 + depth searches, plus up to ESCALATION_QUERIES more if the seed has
    no advertisers of its own. `client.searches_used` is the truth for the run;
    the disk cache means a repeated call costs nothing.

    Raises ValueError for an off-market or empty seed - before any search.
    """
    seed = " ".join((seed or "").split())
    location = location or DEFAULT_LOCATION
    if not tokenize(seed):
        raise ValueError("keywords must contain at least one word of 3 or more characters")
    if not is_coffee(seed):
        raise ValueError(OFF_MARKET_MESSAGE)

    depth = max(0, min(depth, MAX_DEPTH))
    limit = max(1, min(limit, MAX_LIMIT))

    queries, demand, reserve = plan_queries(client, seed, depth, gl=gl, fresh=fresh)
    ads, related, warnings = _scan(client, queries, location, gl, fresh)

    # A seed nobody advertises against is not a dead end: it usually means the query is a map
    # lookup or a question, and the market behind it sits one rung up the commercial ladder.
    escalated: list[str] = []
    if depth and len({a["advertiser_domain"] for a in ads}) < ESCALATION_FLOOR:
        escalated = [q for q in reserve if q not in queries][:ESCALATION_QUERIES]
        more_ads, more_related, more_warnings = _scan(client, escalated, location, gl, fresh)
        ads += more_ads
        related |= more_related
        warnings += more_warnings
        queries += escalated

    # "No ads anywhere" is real data and stays a 200 - plenty of coffee queries carry no paid
    # block. Every query erroring is not: there is nothing to report, so say so.
    if not ads and warnings and len(warnings) >= len(queries):
        raise SerpApiError(f"every query failed: {warnings[0]['error']}")

    rows = rank(ads, seed=seed, demand=demand, related=related, limit=limit)
    advertisers = _advertiser_rollup(ads)
    per_query = {q: {a["advertiser_domain"] for a in ads if a["query"] == q} for q in queries}
    exposed = sum(1 for a in ads if a["targeting_keywords"])

    return {
        "query": seed,
        "location": location,
        "searches_used": client.searches_used,
        "summary": {
            "queries_scanned": len(queries),
            "ads_seen": len(ads),
            "advertisers": len(advertisers),
            "keywords_found": len(rows),
            "keywords_recovered_from_ads": sum(1 for r in rows if r["recovered_from_ad"]),
            "ads_exposing_a_keyword": exposed,
            "competition": band(len(per_query.get(seed.lower(), set()))),
            "confidence": "high" if any(r["recovered_from_ad"] for r in rows) else "medium" if ads else "low",
            "escalated_to": escalated,
        },
        "scoring": SCORING,
        "queries": [{"query": q, "advertisers": len(per_query.get(q, set())), "ads": sum(1 for a in ads if a["query"] == q)} for q in queries],
        "keywords": rows[:limit],
        "advertisers": advertisers,
        "warnings": warnings,
    }


def _advertiser_rollup(ads: list[dict]) -> list[dict]:
    by_domain: dict[str, dict[str, Any]] = {}
    for ad in ads:
        r = by_domain.setdefault(ad["advertiser_domain"], {"ads": 0, "keywords": set(), "queries": set(), "titles": []})
        r["ads"] += 1
        r["keywords"].update(ad["targeting_keywords"])
        r["queries"].add(ad["query"])
        if ad["title"] and len(r["titles"]) < 3:
            r["titles"].append(ad["title"])
    rows = [
        {
            "advertiser_domain": d,
            "ads": r["ads"],
            "recovered_keywords": sorted(r["keywords"]),
            "seen_on_queries": sorted(r["queries"]),
            "sample_titles": r["titles"],
        }
        for d, r in by_domain.items()
    ]
    rows.sort(key=lambda r: (-len(r["recovered_keywords"]), -r["ads"], r["advertiser_domain"]))
    return rows
