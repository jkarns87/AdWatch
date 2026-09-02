"""Anthropic token pricing.

Rates are USD per 1M tokens, (input, output), from Anthropic's published pricing.

A model missing from this table is *unpriced*, not free: `cost_usd` returns None so
the caller records the tokens, leaves cost at zero, and counts the call as unpriced.
Silently costing an unknown model at 0.0 would under-report spend on a page whose
entire job is being right about money — and the config default (`claude-sonnet-4-5`,
see config.py) is exactly such a model.
"""

from __future__ import annotations

RATES: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Cache reads bill at roughly a tenth of the input rate; writes at a premium over it.
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25

_PER_TOKEN = 1_000_000


def is_priced(model: str) -> bool:
    """True when `model` has a published rate and can therefore be costed."""
    return model in RATES


def cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float | None:
    """USD for one call, or None when the model has no published rate."""
    rate = RATES.get(model)
    if rate is None:
        return None
    rate_in, rate_out = rate
    return (
        input_tokens * rate_in
        + output_tokens * rate_out
        + cache_read_tokens * rate_in * CACHE_READ_MULT
        + cache_write_tokens * rate_in * CACHE_WRITE_MULT
    ) / _PER_TOKEN
