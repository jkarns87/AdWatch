"""Strip credentials from text before it reaches a log line or a database column.

The motivating case: httpx puts the full request URL in its exception message, so a
failed webhook POST wrote a complete Slack token into alerts.error and printed it to
stdout. Anything derived from an exception, a URL, or user config should pass through
here first.

Redaction keeps the identifying prefix and masks the secret material — a fully masked
string is useless for debugging, and people switch off tooling that blinds them.
"""

from __future__ import annotations

import re

MASK = "***"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Slack: /services/<team>/<bot>/<token> — mask only the token.
    (re.compile(r"(https?://[^\s'\"]*?/services/[^\s'\"/]+/[^\s'\"/]+/)[^\s'\"/]+"), r"\1" + MASK),
    # Discord: /webhooks/<id>/<token>
    (re.compile(r"(https?://[^\s'\"]*?/webhooks/\d+/)[^\s'\"/]+"), r"\1" + MASK),
    # Secret-bearing query or key=value pairs, in a URL or bare in a message.
    (
        re.compile(r"\b((?:api_key|apikey|access_token|token|secret|password|passwd|pwd)=)[^\s&'\"]+", re.I),
        r"\1" + MASK,
    ),
    # Anthropic keys — the sk-ant- prefix identifies which credential failed.
    (re.compile(r"\b(sk-ant-)[A-Za-z0-9_\-]{8,}"), r"\1" + MASK),
    # SerpApi keys are 64 hex characters.
    (re.compile(r"\b[0-9a-fA-F]{64}\b"), MASK),
    # Bearer tokens in an Authorization header echoed into an error.
    (re.compile(r"\b(Bearer\s+)[A-Za-z0-9._\-]{12,}", re.I), r"\1" + MASK),
)


def redact(text: str | None) -> str:
    """Return `text` with known credential shapes masked. Safe on None."""
    if not text:
        return ""
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out
