"""The analyst's call into the Anthropic SDK.

There was no test here, which is how this shipped: the analyst passed `temperature=0.2`,
anthropic 1.x does not accept it on Messages.create(), every call raised TypeError, the
broad `except Exception` caught it, and the deterministic fallback wrote every insight.

It was silent by construction. The product looked fine — insights appeared, cards
rendered — and the only trace was `status="fallback"` in the llm_calls ledger and a
"0 tokens" figure on the dashboard that read like a metering bug rather than a dead
feature. In production every one of 25 analyst calls fell back and Claude was never
reached once.

So these tests check the call itself, against the *installed* SDK signature, rather than
against a permissive fake. A stub that accepts **kwargs would have passed the whole time.
"""

import inspect
from typing import Any

import pytest

from app.engine.analyst import Analyst

CHANGES = [
    {"id": 1, "kind": "creative_launched", "subject_type": "competitor", "subject_id": 7,
     "subject_label": "RoastNest", "severity": "high", "payload": {"count": 4}},
    {"id": 2, "kind": "serp_position_shift", "subject_type": "competitor", "subject_id": 7,
     "subject_label": "RoastNest", "severity": "medium", "payload": {"from": 4, "to": 1}},
]
CONTEXT = {"watchlist": "Coffee", "vertical": "coffee", "geo": "US"}


def _sdk_create_parameters() -> set[str]:
    """The kwargs the installed anthropic SDK actually accepts on Messages.create()."""
    import anthropic

    sig = inspect.signature(anthropic.resources.messages.Messages.create)
    return set(sig.parameters) - {"self"}


class _Recorder:
    """Fake client that records kwargs and returns a well-formed message."""

    def __init__(self):
        self.kwargs: dict[str, Any] = {}
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs

        class _Block:
            text = '{"summary": "s", "why_it_matters": "w", "recommended_actions": [], "confidence": 0.8}'

        class _Usage:
            input_tokens, output_tokens = 100, 50
            cache_read_input_tokens = cache_creation_input_tokens = 0

        class _Msg:
            content = [_Block()]
            usage = _Usage()

        return _Msg()


def _run(analyst: Analyst) -> dict[str, Any]:
    return analyst.analyze_cluster(CONTEXT, CHANGES)


def test_every_kwarg_the_analyst_sends_is_one_the_installed_sdk_accepts():
    """The actual bug. `temperature` is not in anthropic 1.x's Messages.create()."""
    a = Analyst(api_key="k", model="claude-sonnet-5")
    rec = _Recorder()
    a._client = rec
    _run(a)

    allowed = _sdk_create_parameters()
    # Only assert if the SDK exposes a concrete signature; a **kwargs-only signature
    # would make this vacuous and we would rather know than pretend.
    assert allowed and allowed != {"kwargs"}, "cannot introspect SDK signature"
    unknown = set(rec.kwargs) - allowed
    assert not unknown, f"analyst sends kwargs the SDK rejects: {sorted(unknown)}"


def test_a_successful_call_is_not_reported_as_a_fallback():
    """The fallback is honest about itself — it sets model='fallback' and confidence 0.
    A real answer must not look like one."""
    a = Analyst(api_key="k", model="claude-sonnet-5")
    a._client = _Recorder()
    out = _run(a)
    assert out["model"] == "claude-sonnet-5"
    assert out["summary"] == "s"
    assert out["confidence"] == pytest.approx(0.8)


def test_token_usage_survives_so_the_ledger_can_price_the_call():
    a = Analyst(api_key="k", model="claude-sonnet-5")
    a._client = _Recorder()
    usage = _run(a)["_usage"]
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50


class _Truncated:
    """The model ran out of output budget mid-JSON — what actually happened in
    production, where three of seven briefs stopped at exactly the 900-token cap."""

    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        class _Block:
            text = '{"summary": "BeanLoop dropped two text ads and relaunched a Bay Area", "why_it_matters": "They see it as a stron'

        class _Usage:
            input_tokens, output_tokens = 900, 900
            cache_read_input_tokens = cache_creation_input_tokens = 0

        class _Msg:
            content = [_Block()]
            usage = _Usage()
            stop_reason = "max_tokens"

        return _Msg()


def test_a_brief_cut_off_by_the_token_cap_is_not_rendered_as_raw_json():
    """The insight card showed a wall of unterminated JSON at 0% confidence. A truncated
    answer is a failed answer; the honest fallback is better than the debris."""
    a = Analyst(api_key="k", model="claude-sonnet-5")
    a._client = _Truncated()
    out = _run(a)
    assert out["model"] == "fallback"
    assert '{"summary"' not in out["summary"]
    assert "truncated" in out["why_it_matters"].lower()


def test_the_token_cap_leaves_room_for_a_full_brief():
    """Measured in production: briefs land at 498-609 output tokens, and every one that
    hit 900 was cut off. 900 was not headroom, it was the median-plus-a-bit."""
    a = Analyst(api_key="k", model="claude-sonnet-5")
    rec = _Recorder()
    a._client = rec
    _run(a)
    assert rec.kwargs["max_tokens"] >= 1500


def test_prose_that_is_not_json_is_still_shown_rather_than_discarded():
    """Degrading to a readable summary is deliberate (see the module docstring). Only
    JSON debris is worth throwing away."""

    class _Prose:
        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            class _Block:
                text = "RoastNest launched four video creatives overnight."

            class _Msg:
                content = [_Block()]
                usage = None
                stop_reason = "end_turn"

            return _Msg()

    a = Analyst(api_key="k", model="claude-sonnet-5")
    a._client = _Prose()
    out = _run(a)
    assert out["summary"] == "RoastNest launched four video creatives overnight."


def test_a_transport_error_still_falls_back_rather_than_crashing_a_run():
    """The fallback exists for a reason and must stay — a dead model should not fail
    the whole collection."""

    class _Boom:
        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            raise RuntimeError("upstream is down")

    a = Analyst(api_key="k", model="claude-sonnet-5")
    a._client = _Boom()
    out = _run(a)
    assert out["model"] == "fallback"
    assert "upstream is down" in out["why_it_matters"]


def test_no_key_falls_back_without_attempting_a_call(monkeypatch):
    # An empty api_key argument falls through to the platform key by design, so the
    # platform key has to be cleared for there to be genuinely no key.
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "", raising=False)
    a = Analyst(api_key="", model="claude-sonnet-5")
    out = _run(a)
    assert out["model"] == "fallback"
    assert "ANTHROPIC_API_KEY not set" in out["why_it_matters"]
