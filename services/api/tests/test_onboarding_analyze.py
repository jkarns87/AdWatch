"""Reading a company's site and turning it into a watchlist proposal.

Everything here is untrusted twice over: the page is written by a third party, and
the model's answer is free-form JSON. Nothing is persisted from this module — it
proposes, and the caller verifies.
"""

import json
import sys
from types import SimpleNamespace

from app.onboarding import analyze as ana

GOOD = {
    "vertical_id": 71,
    "keywords": ["coffee subscription", "single origin beans"],
    "competitors": [
        {"domain": "bluebottlecoffee.com", "name": "Blue Bottle", "reason": "national DTC roaster"},
        {"domain": "https://www.sightglasscoffee.com/shop", "name": "Sightglass", "reason": "SF roaster"},
    ],
    "assets": [
        {"kind": "brand", "key": "primary_color", "value": "#B5121B"},
        {"kind": "property", "key": "landing_page", "value": "/subscriptions"},
    ],
    "site_read": True,
}


def _fake_anthropic(payload, usage=None):
    text = payload if isinstance(payload, str) else json.dumps(payload)

    class Messages:
        @staticmethod
        def create(**kwargs):
            Messages.last = kwargs
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=text)],
                usage=usage or SimpleNamespace(input_tokens=1000, output_tokens=200,
                                               cache_read_input_tokens=0, cache_creation_input_tokens=0),
            )

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

    return SimpleNamespace(Anthropic=Client), Messages


def _run(monkeypatch, payload, **over):
    mod, msgs = _fake_anthropic(payload)
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    kwargs = dict(name="Verve Coffee", domain="vervecoffee.com",
                  description="DTC specialty roaster", api_key="sk-ant-x", model="claude-sonnet-5")
    kwargs.update(over)
    return ana.analyze_company(**kwargs), msgs


def test_a_well_formed_answer_is_parsed(monkeypatch):
    out, _ = _run(monkeypatch, GOOD)
    assert out["vertical"] == {"id": 71, "name": "Food & Drink"}
    assert out["keywords"] == ["coffee subscription", "single origin beans"]
    assert out["site_read"] is True


def test_competitor_domains_are_normalised(monkeypatch):
    """The model returns whatever the page showed — scheme, www, a path."""
    out, _ = _run(monkeypatch, GOOD)
    assert [c["domain"] for c in out["competitors"]] == ["bluebottlecoffee.com", "sightglasscoffee.com"]


def test_the_company_is_not_proposed_as_its_own_competitor(monkeypatch):
    payload = {**GOOD, "competitors": GOOD["competitors"] + [{"domain": "www.vervecoffee.com", "name": "Verve"}]}
    out, _ = _run(monkeypatch, payload)
    assert "vervecoffee.com" not in {c["domain"] for c in out["competitors"]}


def test_entries_without_a_usable_domain_are_dropped(monkeypatch):
    payload = {**GOOD, "competitors": GOOD["competitors"] + [{"name": "Some Cafe"}, {"domain": ""}, {"domain": "not a domain"}]}
    out, _ = _run(monkeypatch, payload)
    assert all(c["domain"] and "." in c["domain"] for c in out["competitors"])


def test_duplicate_competitors_collapse(monkeypatch):
    payload = {**GOOD, "competitors": GOOD["competitors"] + [{"domain": "https://bluebottlecoffee.com/", "name": "dup"}]}
    out, _ = _run(monkeypatch, payload)
    domains = [c["domain"] for c in out["competitors"]]
    assert len(domains) == len(set(domains))


def test_an_invented_vertical_id_becomes_none(monkeypatch):
    """Better no vertical than a category id that does not exist — cat= would 400."""
    out, _ = _run(monkeypatch, {**GOOD, "vertical_id": 999999})
    assert out["vertical"] is None


def test_a_vertical_returned_as_a_string_still_works(monkeypatch):
    out, _ = _run(monkeypatch, {**GOOD, "vertical_id": "71"})
    assert out["vertical"]["id"] == 71


def test_unparseable_output_degrades_instead_of_raising(monkeypatch):
    out, _ = _run(monkeypatch, "I'm sorry, I can't help with that.")
    assert out["vertical"] is None
    assert out["competitors"] == []
    assert out["site_read"] is False


def test_usage_is_surfaced_for_the_ledger(monkeypatch):
    out, _ = _run(monkeypatch, GOOD)
    assert out["_usage"].input_tokens == 1000


def test_no_api_key_returns_an_empty_proposal_rather_than_failing(monkeypatch):
    out, _ = _run(monkeypatch, GOOD, api_key="")
    assert out["competitors"] == [] and out["vertical"] is None
    assert out["_usage"] is None


def test_the_fetch_is_pinned_to_the_submitted_domain(monkeypatch):
    """allowed_domains is the injection control: a link planted in the page must not
    be able to redirect the fetch somewhere else."""
    _, msgs = _run(monkeypatch, GOOD)
    tools = msgs.last["tools"]
    fetch = next(t for t in tools if t["name"] == "web_fetch")
    assert set(fetch["allowed_domains"]) == {"vervecoffee.com", "www.vervecoffee.com"}
    assert fetch["max_content_tokens"] > 0, "an unbounded page can exhaust the budget"


def test_the_url_is_in_the_prompt_or_web_fetch_cannot_use_it(monkeypatch):
    """web_fetch only retrieves URLs already present in the conversation."""
    _, msgs = _run(monkeypatch, GOOD)
    assert "vervecoffee.com" in json.dumps(msgs.last["messages"])
