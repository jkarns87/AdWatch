"""Response models for the coffee endpoints. Kept here so app/schemas.py stays untouched."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Signals(BaseModel):
    targeting_keyword_advertisers: int
    sponsored_query_advertisers: int
    ad_copy_advertisers: int
    autocomplete_rank: int | None = None
    autocomplete_relevance_share: float | None = None
    related_search: bool


class ExampleAd(BaseModel):
    advertiser_domain: str
    title: str | None = None
    description: str | None = None
    displayed_link: str | None = None


class KeywordOut(BaseModel):
    keyword: str
    score: float                       # 0-100 on the fixed scale published in `scoring`
    evidence: Literal["targeting_keyword", "sponsored_query", "ad_copy", "autocomplete"]
    recovered_from_ad: bool            # the advertiser's own ad URL named it
    advertiser_count: int
    advertisers: list[str]
    competition: Literal["high", "medium", "low", "none"]
    match_types: list[str] = Field(default_factory=list)   # broad | phrase | exact
    ads: int
    signals: Signals
    seen_on_queries: list[str] = Field(default_factory=list)
    example_ad: ExampleAd | None = None


class AdvertiserOut(BaseModel):
    advertiser_domain: str
    ads: int
    recovered_keywords: list[str] = Field(default_factory=list)
    seen_on_queries: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)


class ScannedQuery(BaseModel):
    query: str
    advertisers: int
    ads: int


class Summary(BaseModel):
    queries_scanned: int
    ads_seen: int
    advertisers: int
    keywords_found: int
    keywords_recovered_from_ads: int
    ads_exposing_a_keyword: int        # the rest stripped Google's {keyword} macro
    competition: Literal["high", "medium", "low", "none"]
    confidence: Literal["high", "medium", "low"]
    escalated_to: list[str] = Field(default_factory=list)


class KeywordsOut(BaseModel):
    query: str
    location: str | None = None
    searches_used: int                 # SerpApi searches this request spent
    summary: Summary
    scoring: dict[str, Any]            # formula + weights + bands, so a score can be recomputed
    queries: list[ScannedQuery]
    keywords: list[KeywordOut]
    advertisers: list[AdvertiserOut]
    warnings: list[dict[str, str]] = Field(default_factory=list)


class ImportedWatchlist(BaseModel):
    watchlist_id: int
    name: str
    competitors: list[str]
    keywords: list[str]
