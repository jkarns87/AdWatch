"""Brand conquesting — who is paying for someone else's name.

Measured against the live API on 2026-09-03: 7 of 8 brand SERPs carried ads, every
one of those had a competitor bidding on the brand, and in 4 of 7 the brand owner was
absent from its own name. Engine choice decides whether any of it is visible —
`engine=google` reported zero conquerors on a brand term where two rivals were
actively bidding, which is one more reason the collector uses `google_ads`.

A rival on your brand term is spending money to intercept customers who already asked
for you by name, and being absent from your own term means paying nothing to defend
it. Both are high severity and neither is visible anywhere else in the product.

Costs one search per brand term per run. Brand terms deliberately skip the trends and
related-query calls an ordinary keyword makes: demand for a brand name is not the
signal here, and charging three searches for one would be waste.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from .diff import _chg


def brand_term(competitor: Any) -> str:
    """The query to run for a competitor's brand.

    Their name if they have one, otherwise the registrable label of their domain —
    "dunkindonuts.com" becomes "dunkindonuts", which is what someone types.
    """
    name = (getattr(competitor, "name", "") or "").strip()
    if name:
        return name
    domain = (getattr(competitor, "domain", "") or "").strip().lower()
    return domain.split(".")[0] if domain else ""


def ensure_brand_terms(db: Any, watchlist: Any) -> list[Any]:
    """Give every competitor a brand keyword, including our own.

    The self competitor is excluded from user-facing counts and plan limits, not from
    brand monitoring — defending your own name is the whole point. Idempotent, and
    keyed on (owner, kind) rather than on the term, so a customer who already tracks
    their own brand as an ordinary market keyword keeps both rows: they cost
    different amounts to collect and answer different questions.
    """
    from .. import models as m

    existing = {
        k.owner_competitor_id
        for k in db.scalars(
            select(m.Keyword).where(m.Keyword.watchlist_id == watchlist.id, m.Keyword.kind == "brand")
        ).all()
    }
    made: list[Any] = []
    for comp in watchlist.competitors:
        if comp.id in existing:
            continue
        term = brand_term(comp)
        if not term:
            continue
        kw = m.Keyword(watchlist_id=watchlist.id, term=term, kind="brand", owner_competitor_id=comp.id)
        db.add(kw)
        made.append(kw)
    return made


def _is_owner(domain: str, owner_domain: str) -> bool:
    """Whether an advertiser domain belongs to the brand owner.

    Subdomains count — shop.owner.com is the brand defending itself. A plain suffix
    test would also match notowner.com, which is a lookalike and exactly the sort of
    advertiser worth alerting on, so the label boundary has to be respected.
    """
    d, o = domain.lower().strip(), owner_domain.lower().strip()
    if not d or not o:
        return False
    return d == o or d.endswith("." + o)


def assess(ads: list[dict], *, owner_domain: str) -> dict[str, Any]:
    """The current state of one brand's paid block."""
    conquerors = [a for a in ads if not _is_owner(a.get("advertiser_domain", ""), owner_domain)]
    owner = next((a for a in ads if _is_owner(a.get("advertiser_domain", ""), owner_domain)), None)
    return {
        "owner_present": owner is not None,
        "owner_position": owner.get("position") if owner else None,
        "conquerors": conquerors,
        # Nobody bidding at all — the owner included — is the normal, healthy state
        # for a brand term, not an emergency. Undefended means someone is attacking
        # and the owner is not there.
        "undefended": owner is None and bool(conquerors),
    }


def diff_brand(
    previous: list[dict] | None,
    current: list[dict],
    *,
    owner_domain: str,
    competitor_id: int,
    label: str,
) -> list[dict]:
    """Changes in who is bidding on one brand's name.

    Events, not state: a standing conqueror is re-announced on no run, because the
    paid block is measurably flaky — repeated identical calls returned zero ads 44%
    of the time — and re-reporting it every run would bury the run where one actually
    arrives. Current state is exposed through the API instead.
    """
    if previous is None:
        return []
    before, after = assess(previous, owner_domain=owner_domain), assess(current, owner_domain=owner_domain)
    prev_domains = {a["advertiser_domain"] for a in before["conquerors"]}
    cur_domains = {a["advertiser_domain"] for a in after["conquerors"]}

    changes: list[dict] = []
    for a in after["conquerors"]:
        if a["advertiser_domain"] in prev_domains:
            continue
        changes.append(
            _chg("brand_conquest", "high", "competitor", competitor_id, label, {
                "brand": label,
                "advertiser_domain": a["advertiser_domain"],
                "position": a.get("position"),
                "block": a.get("block"),
                "title": a.get("title"),
                "owner_present": after["owner_present"],
            })
        )
    for d in prev_domains - cur_domains:
        changes.append(
            _chg("brand_conquest_ended", "low", "competitor", competitor_id, label,
                 {"brand": label, "advertiser_domain": d})
        )

    # Only meaningful while someone is actually bidding on the term. An empty block
    # means the auction went quiet, which is not the owner losing ground.
    if current:
        if before["owner_present"] and not after["owner_present"] and after["conquerors"]:
            changes.append(
                _chg("brand_undefended", "high", "competitor", competitor_id, label, {
                    "brand": label,
                    "conquerors": sorted(cur_domains),
                    "was_at_position": before["owner_position"],
                })
            )
        elif not before["owner_present"] and after["owner_present"]:
            changes.append(
                _chg("brand_defended", "low", "competitor", competitor_id, label,
                     {"brand": label, "position": after["owner_position"]})
            )
    return changes
