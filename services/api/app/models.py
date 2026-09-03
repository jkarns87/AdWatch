"""SQLAlchemy models — mirrors docs/ARCHITECTURE.md § Data model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    xano_workspace_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    vertical: Mapped[str] = mapped_column(String(200), default="")
    geo: Mapped[str] = mapped_column(String(10), default="US")
    location: Mapped[str | None] = mapped_column(String(120))  # SerpApi `location` for Google Search, e.g. "San Francisco, California, United States"
    # Google Trends taxonomy node (app/taxonomy.py); `vertical` stays the human label.
    trends_category_id: Mapped[int | None] = mapped_column(Integer)
    company_domain: Mapped[str | None] = mapped_column(String(255))
    # What Claude was given at onboarding, kept so a re-analysis is reproducible.
    company_description: Mapped[str | None] = mapped_column(Text)
    # Drift guard for keyword scans (app/market.py). Different from
    # trends_category_id: that scopes cat= on demand, these decide whether a
    # keyword belongs to this market at all.
    market_terms: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    competitors: Mapped[list[Competitor]] = relationship(back_populates="watchlist", cascade="all, delete-orphan")
    keywords: Mapped[list[Keyword]] = relationship(back_populates="watchlist", cascade="all, delete-orphan")


class Competitor(Base):
    __tablename__ = "competitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(255))
    advertiser_id: Mapped[str | None] = mapped_column(String(100))
    # The workspace's own domain, tracked so SERP reads answer "where am I versus them".
    # Excluded from user-facing competitor counts and plan limits; included in collection
    # and share of voice. See tests/test_self_competitor.py for the rule.
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist: Mapped[Watchlist] = relationship(back_populates="competitors")
    creatives: Mapped[list[Creative]] = relationship(back_populates="competitor", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    term: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watchlist: Mapped[Watchlist] = relationship(back_populates="keywords")


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | failed
    searches_used: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # ads_transparency | search_ads | trends | related_queries
    subject_type: Mapped[str] = mapped_column(String(20))  # competitor | keyword
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    serpapi_search_id: Mapped[str | None] = mapped_column(String(100))
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nullable so retention can drop the payload and keep the row: the metadata above is
    # the audit trail for a fetch, and it costs a few bytes against ~27 kB for `raw`.
    # none_as_null because JSON otherwise stores Python None as the JSON literal `null`,
    # which still occupies the column and still satisfies IS NOT NULL — retention would
    # free nothing and re-prune the same rows on every pass.
    raw: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))


class Creative(Base):
    __tablename__ = "creatives"
    __table_args__ = (UniqueConstraint("competitor_id", "creative_id", name="uq_creative_per_competitor"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), index=True)
    creative_id: Mapped[str] = mapped_column(String(100))
    format: Mapped[str] = mapped_column(String(20), default="text")  # text | image | video
    platform: Mapped[str | None] = mapped_column(String(40))
    target_domain: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(Text)
    details_url: Mapped[str | None] = mapped_column(Text)
    first_shown: Mapped[date | None] = mapped_column(Date)
    last_shown: Mapped[date | None] = mapped_column(Date)
    text: Mapped[dict | None] = mapped_column(JSON)  # {headline, description} when available
    # Days actually served, not the span between first and last shown — a creative can
    # run 490 of the 520 days between them, or 12. Separates evergreen from test.
    total_days_shown: Mapped[int | None] = mapped_column(Integer)
    first_seen_run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    last_seen_run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    competitor: Mapped[Competitor] = relationship(back_populates="creatives")


class SerpAd(Base):
    __tablename__ = "serp_ads"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    block: Mapped[str] = mapped_column(String(10), default="top")  # top | bottom
    advertiser_domain: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str | None] = mapped_column(Text)
    displayed_link: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))  # advertiser display name, e.g. "Nespresso®"
    sitelinks: Mapped[list | None] = mapped_column(JSON)  # titles only; the hrefs are unstable redirects


class ProductListing(Base):
    """Product listings from the paid-search response's `immersive_products` block.

    Separate from SerpAd on purpose: these rows carry no click-tracking link, so they
    evidence merchandising presence and price rather than paid placement.
    """

    __tablename__ = "product_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    merchant: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    original_price: Mapped[float | None] = mapped_column(Float)
    promo: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[float | None] = mapped_column(Float)
    reviews: Mapped[int | None] = mapped_column(Integer)


class TrendPoint(Base):
    __tablename__ = "trend_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[int] = mapped_column(Integer)


class RelatedQuery(Base):
    __tablename__ = "related_queries"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    bucket: Mapped[str] = mapped_column(String(10))  # rising | top
    value_text: Mapped[str] = mapped_column(String(40), default="")
    value_num: Mapped[float | None] = mapped_column(Float)


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    subject_type: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[int] = mapped_column(Integer)
    subject_label: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    insight_id: Mapped[int | None] = mapped_column(ForeignKey("insights.id"), index=True)


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    model: Mapped[str] = mapped_column(String(100), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    recommended_actions: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyAsset(Base):
    """One extracted fact about the company. A narrow table rather than wide columns:
    the kinds have nothing in common and more will follow. Their own ad creatives are
    NOT here — those are Creative rows against the is_self competitor, so
    creative_launched fires on the user's own ads for free."""

    __tablename__ = "company_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # brand | property | catalogue
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceSecret(Base):
    """A customer-supplied API key, encrypted at rest.

    Only `last4` is stored in clear, and it is the only part that may be shown back
    to a user. `ciphertext` must never leave the API in any response — see
    app/workspace_secrets.py, which is the sole reader.
    """

    __tablename__ = "workspace_secrets"
    __table_args__ = (UniqueConstraint("workspace_id", "kind", name="uq_secret_per_workspace_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # serpapi | anthropic
    ciphertext: Mapped[str] = mapped_column(Text)
    last4: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LlmCall(Base):
    """One row per Claude call, from every call site. Cost is frozen at write time so
    historical spend stays correct when Anthropic changes prices; tokens are kept so it
    can be recomputed if a rate was ever wrong.

    A ledger rather than columns on Insight because reports/data.py calls Claude without
    producing an Insight — columns there would miss report generation entirely.
    """

    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, index=True)
    watchlist_id: Mapped[int | None] = mapped_column(ForeignKey("watchlists.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), index=True)
    feature: Mapped[str] = mapped_column(String(20))  # analyst | report
    model: Mapped[str] = mapped_column(String(100), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    priced: Mapped[bool] = mapped_column(Boolean, default=True)  # False = model has no published rate
    status: Mapped[str] = mapped_column(String(12), default="ok")  # ok | error | fallback
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("insights.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="webhook")
    target: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
