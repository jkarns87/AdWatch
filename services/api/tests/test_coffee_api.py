"""GET /api/v1/coffee/keywords over the real ASGI app, with SerpApi stubbed out."""

import pytest
from fastapi.testclient import TestClient

from app.coffee import router as route
from app.collectors.serpapi_client import SerpApiError
from app.main import app
from tests.test_coffee_keywords import AD, BARE_AD, StubClient


@pytest.fixture
def client(monkeypatch):
    stub = StubClient(
        {"coffee subscription": [AD, BARE_AD]},
        suggestions=[{"value": "coffee subscription reviews", "relevance": 900}],
    )
    monkeypatch.setattr(route, "SerpApiClient", lambda *a, **k: stub)
    yield TestClient(app), stub


def test_json_is_the_default_output(client):
    c, _ = client
    r = c.get("/api/v1/coffee/keywords", params={"keywords": "coffee subscription", "depth": 0})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["query"] == "coffee subscription"
    assert body["summary"]["ads_exposing_a_keyword"] == 1
    assert body["scoring"]["reference"] == 30.0
    top = body["keywords"][0]
    assert top["keyword"] == "coffee subscription" and top["evidence"] == "targeting_keyword"
    assert top["example_ad"]["advertiser_domain"] == "drinktrade.example"


def test_markdown_and_html_outputs(client):
    c, _ = client
    md = c.get("/api/v1/coffee/keywords", params={"keywords": "coffee subscription", "output": "md", "depth": 0})
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert "# Coffee keywords" in md.text and "coffee subscription" in md.text

    html = c.get("/api/v1/coffee/keywords", params={"keywords": "coffee subscription", "output": "html", "depth": 0})
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert html.text.startswith("<!doctype html>") and "</html>" in html.text


def test_html_escapes_the_seed(client):
    c, _ = client
    r = c.get("/api/v1/coffee/keywords", params={"keywords": 'coffee "<script>"', "output": "html", "depth": 0})
    assert r.status_code == 200 and "<script>" not in r.text


def test_an_off_market_keyword_is_400_and_costs_nothing(client):
    c, stub = client
    r = c.get("/api/v1/coffee/keywords", params={"keywords": "running shoes"})
    assert r.status_code == 400 and "coffee" in r.json()["detail"]
    assert stub.searches_used == 0


def test_bad_parameters_are_422_from_the_schema(client):
    c, _ = client
    assert c.get("/api/v1/coffee/keywords").status_code == 422                                     # keywords is required
    assert c.get("/api/v1/coffee/keywords", params={"keywords": "coffee", "output": "pdf"}).status_code == 422
    assert c.get("/api/v1/coffee/keywords", params={"keywords": "coffee", "depth": 99}).status_code == 422
    assert c.get("/api/v1/coffee/keywords", params={"keywords": "coffee", "limit": 0}).status_code == 422


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, 401), (403, 401), (429, 429), (500, 502)],
)
def test_upstream_failures_map_to_the_documented_statuses(monkeypatch, status, expected):
    stub = StubClient(fail={"coffee subscription": SerpApiError(f"SerpApi {status}: upstream said no")})
    monkeypatch.setattr(route, "SerpApiClient", lambda *a, **k: stub)
    r = TestClient(app).get("/api/v1/coffee/keywords", params={"keywords": "coffee subscription", "depth": 0})
    assert r.status_code == expected
