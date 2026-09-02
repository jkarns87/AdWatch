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
    raw: Mapped[dict] = mapped_column(JSON)


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


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("insights.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="webhook")
    target: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
