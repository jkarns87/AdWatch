"""Pydantic response/request models — mirrors docs/API_CONTRACT.md."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- watchlists ---------------------------------------------------------------------------------


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    vertical: str = ""
    geo: str = "US"
    location: str | None = Field(default=None, max_length=120)  # SerpApi location string for Google Search


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=255)
    advertiser_id: str | None = None


class KeywordCreate(BaseModel):
    term: str = Field(min_length=1, max_length=255)


class RunOut(ORM):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    searches_used: int
    error: str | None = None


class CompetitorOut(ORM):
    id: int
    name: str
    domain: str
    advertiser_id: str | None
    active_creatives: int = 0


class KeywordOut(ORM):
    id: int
    term: str


class WatchlistSummary(BaseModel):
    id: int
    name: str
    vertical: str
    geo: str
    location: str | None = None
    competitor_count: int
    keyword_count: int
    last_run_at: datetime | None
    open_changes: int


class WatchlistDetail(BaseModel):
    id: int
    name: str
    vertical: str
    geo: str
    location: str | None = None
    created_at: datetime
    competitors: list[CompetitorOut]
    keywords: list[KeywordOut]
    last_run: RunOut | None


# ---- read models --------------------------------------------------------------------------------


class ChangeOut(ORM):
    id: int
    run_id: int
    kind: str
    severity: str
    subject_type: str
    subject_id: int
    subject_label: str
    detected_at: datetime
    insight_id: int | None
    payload: dict[str, Any]


class ActionOut(BaseModel):
    action: str = ""
    rationale: str = ""
    effort: str = ""
    urgency: str = ""


class InsightOut(ORM):
    id: int
    run_id: int
    created_at: datetime
    model: str
    confidence: float
    summary: str
    why_it_matters: str
    recommended_actions: list[dict[str, Any]]
    change_ids: list[int] = []
    changes: list[ChangeOut] = []


class CreativeOut(ORM):
    id: int
    competitor_id: int
    creative_id: str
    format: str
    platform: str | None
    target_domain: str | None
    image_url: str | None
    details_url: str | None
    first_shown: date | None
    last_shown: date | None
    active: bool
    first_seen_run_id: int
    last_seen_run_id: int
    text: dict[str, Any] | None


class SerpAdOut(BaseModel):
    position: int
    block: str
    advertiser_domain: str
    title: str
    description: str | None
    displayed_link: str | None
    is_tracked_competitor: bool
    competitor_id: int | None


class ShareOfVoice(BaseModel):
    advertiser_domain: str
    appearances: int
    avg_position: float


class SerpOut(BaseModel):
    keyword: KeywordOut
    run_id: int | None
    ads: list[SerpAdOut]
    share_of_voice: list[ShareOfVoice]


class TrendPointOut(BaseModel):
    date: date
    value: int


class RelatedOut(BaseModel):
    query: str
    value_text: str
    value_num: float | None


class TrendsOut(BaseModel):
    keyword: KeywordOut
    run_id: int | None
    timeline: list[TrendPointOut]
    related_rising: list[RelatedOut]
    related_top: list[RelatedOut]


class CollectOut(BaseModel):
    run: RunOut
    snapshots: int
    changes: list[ChangeOut]


class AnalyzeOut(BaseModel):
    insights: list[InsightOut]
    alerts_sent: int


class CollectAnalyzeOut(BaseModel):
    run: RunOut
    snapshots: int
    changes: list[ChangeOut]
    insights: list[InsightOut]
    alerts_sent: int


class SeedIn(BaseModel):
    mode: Literal["synthetic", "live"] = "synthetic"
    vertical: str | None = None


class SeedOut(BaseModel):
    watchlist_id: int
    runs: list[int]
    changes: int
    insights: int


# ---- usage & budget --------------------------------------------------------------------------------


class WatchlistUsage(BaseModel):
    watchlist_id: int
    name: str
    competitors: int
    keywords: int
    searches_used: int
    runs: int
    last_run_at: datetime | None
    searches_per_run: int
    projected_month_current: int
    projected_month_plan: int
    over_plan_limits: bool
    llm_cost_usd: float = 0.0  # Claude spend attributed to this watchlist


class LlmFeatureCost(BaseModel):
    feature: str
    calls: int
    cost_usd: float


class LlmModelCost(BaseModel):
    model: str
    calls: int
    cost_usd: float


class LlmUsage(BaseModel):
    calls: int
    cost_usd: float
    unpriced_calls: int  # models with no published rate; tokens recorded, cost unknown
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    by_feature: list[LlmFeatureCost]
    by_model: list[LlmModelCost]
    metering_since: datetime | None  # None until the first call is recorded


class UsageOut(BaseModel):
    workspace_id: int
    plan: str
    period_start: datetime
    period_end: datetime
    searches_used: int
    searches_budget: int
    searches_remaining: int
    budget_used_pct: float
    runs: int
    cost_to_date_usd: float
    projected_month_current_cadence: int
    projected_month_plan_cadence: int
    projected_cost_current_usd: float
    projected_cost_plan_usd: float
    rate_per_search_usd: float
    watchlists_used: int
    watchlists_limit: int
    by_watchlist: list[WatchlistUsage]
    plans: list[dict[str, Any]]
    llm: LlmUsage
    total_cost_usd: float  # SerpApi searches + Claude tokens
