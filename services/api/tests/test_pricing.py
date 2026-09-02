"""Anthropic token pricing. Money is on a dashboard, so an unknown model must be
loudly unpriced rather than quietly free."""

import pytest

from app import pricing


def test_input_tokens_priced_at_the_model_rate():
    # claude-sonnet-5 is $2.00 per 1M input tokens
    assert pricing.cost_usd("claude-sonnet-5", input_tokens=1_000_000) == pytest.approx(2.00)


def test_output_tokens_priced_higher_than_input():
    # $10.00 per 1M output tokens
    assert pricing.cost_usd("claude-sonnet-5", output_tokens=1_000_000) == pytest.approx(10.00)


def test_input_and_output_are_summed():
    cost = pricing.cost_usd("claude-sonnet-5", input_tokens=500_000, output_tokens=100_000)
    assert cost == pytest.approx(1.00 + 1.00)


def test_cache_reads_bill_at_a_tenth_of_input():
    assert pricing.cost_usd("claude-sonnet-5", cache_read_tokens=1_000_000) == pytest.approx(0.20)


def test_cache_writes_bill_above_input():
    assert pricing.cost_usd("claude-sonnet-5", cache_write_tokens=1_000_000) == pytest.approx(2.50)


def test_opus_costs_more_than_sonnet_for_the_same_tokens():
    sonnet = pricing.cost_usd("claude-sonnet-5", input_tokens=1_000_000)
    opus = pricing.cost_usd("claude-opus-5", input_tokens=1_000_000)
    assert opus > sonnet


def test_unknown_model_is_unpriced_not_free():
    """The config default claude-sonnet-4-5 is not in the rate table. Returning 0.0
    would under-report spend on a page whose whole job is being right about money."""
    assert pricing.cost_usd("claude-sonnet-4-5", input_tokens=1_000_000) is None


def test_is_priced_reports_whether_a_model_can_be_costed():
    assert pricing.is_priced("claude-sonnet-5") is True
    assert pricing.is_priced("claude-sonnet-4-5") is False


def test_zero_tokens_costs_nothing_for_a_known_model():
    assert pricing.cost_usd("claude-sonnet-5") == 0.0
