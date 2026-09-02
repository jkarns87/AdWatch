"""CSV in and out for a watchlist: export it, edit it in a spreadsheet, import it back."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as m
from app.coffee.router import parse_watchlist_csv
from app.db import Base, get_db
from app.main import app

CSV = """type,name,domain,term
competitor,BeanLoop,beanloop.example,
competitor,RoastNest,https://www.roastnest.example/pricing,
keyword,,,coffee subscription
keyword,,,cold brew delivery
"""
HEADERS = {"Content-Type": "text/csv"}


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add(m.Workspace(id=1, name="w"))
        db.add(m.Watchlist(id=1, workspace_id=1, name="Specialty Coffee", vertical="specialty coffee", geo="US"))
        db.add(m.Competitor(id=11, watchlist_id=1, name="BeanLoop", domain="beanloop.example"))
        db.add(m.Keyword(id=21, watchlist_id=1, term="coffee subscription"))
        db.commit()

    def _db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---- parsing -------------------------------------------------------------------------------


def test_urls_and_www_are_reduced_to_a_domain():
    competitors, keywords = parse_watchlist_csv(CSV)
    assert [c["domain"] for c in competitors] == ["beanloop.example", "roastnest.example"]
    assert keywords == ["coffee subscription", "cold brew delivery"]


def test_a_missing_type_column_is_inferred_from_the_data():
    competitors, keywords = parse_watchlist_csv("name,domain,term\nBeanLoop,beanloop.example,\n,,coffee subscription\n")
    assert [c["domain"] for c in competitors] == ["beanloop.example"]
    assert keywords == ["coffee subscription"]


def test_a_competitor_with_no_name_gets_one_from_its_domain():
    competitors, _ = parse_watchlist_csv("type,name,domain,term\ncompetitor,,beanloop.example,\n")
    assert competitors[0]["name"] == "Beanloop"


def test_duplicates_are_dropped_and_order_is_kept():
    _, keywords = parse_watchlist_csv("type,term\nkeyword,coffee subscription\nkeyword,Coffee Subscription\nkeyword,cold brew\n")
    assert keywords == ["coffee subscription", "cold brew"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "no data rows"),
        ("type,name,domain,term\n", "no data rows"),
        ("type,name,domain,term\ncompetitor,BeanLoop,,\n", "needs a domain"),
        ("type,name,domain,term\ncompetitor,BeanLoop,not-a-domain,\n", "not a domain"),
        ("type,name,domain,term\nrobot,x,y,z\n", "unknown type"),
    ],
)
def test_bad_csv_says_what_is_wrong(text, message):
    with pytest.raises(Exception, match=message):
        parse_watchlist_csv(text)


# ---- the routes ----------------------------------------------------------------------------


def test_export_returns_a_downloadable_csv(client):
    r = client.get("/api/v1/watchlists/1/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and ".csv" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "type,name,domain,term"
    assert "competitor,BeanLoop,beanloop.example," in lines
    assert "keyword,,,coffee subscription" in lines


def test_import_builds_a_watchlist_in_one_step(client):
    r = client.post(
        "/api/v1/watchlists/import.csv",
        params={"name": "Imported Coffee", "vertical": "specialty coffee", "location": "San Francisco, California, United States"},
        content=CSV,
        headers=HEADERS,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Imported Coffee"
    assert body["competitors"] == ["beanloop.example", "roastnest.example"]
    assert body["keywords"] == ["coffee subscription", "cold brew delivery"]

    detail = client.get(f"/api/v1/watchlists/{body['watchlist_id']}").json()
    assert detail["location"].startswith("San Francisco")
    assert [k["term"] for k in detail["keywords"]] == ["coffee subscription", "cold brew delivery"]


def test_a_watchlist_survives_a_round_trip(client):
    exported = client.get("/api/v1/watchlists/1/export.csv").text
    r = client.post("/api/v1/watchlists/import.csv", params={"name": "Copy"}, content=exported, headers=HEADERS)
    assert r.status_code == 201
    assert r.json()["competitors"] == ["beanloop.example"]
    assert r.json()["keywords"] == ["coffee subscription"]


def test_import_rejects_junk_with_a_reason(client):
    r = client.post("/api/v1/watchlists/import.csv", params={"name": "Nope"}, content="hello world", headers=HEADERS)
    assert r.status_code == 400 and "expected columns" in r.json()["detail"]


def test_import_needs_a_name(client):
    assert client.post("/api/v1/watchlists/import.csv", content=CSV, headers=HEADERS).status_code == 422


def test_utf8_bom_from_excel_is_handled(client):
    r = client.post(
        "/api/v1/watchlists/import.csv",
        params={"name": "From Excel"},
        content="﻿type,name,domain,term\nkeyword,,,café latte\n".encode(),
        headers=HEADERS,
    )
    assert r.status_code == 201 and r.json()["keywords"] == ["café latte"]


def test_the_framework_routes_still_work(client):
    # The CSV routes are additive: watchlists.py is untouched and still serves its own paths.
    assert client.get("/api/v1/watchlists/1").status_code == 200
    assert client.post("/api/v1/watchlists/1/keywords", json={"term": "espresso beans"}).status_code == 201
