"""Credentials must not reach the database or the logs.

httpx puts the full request URL in its exception message, so a failed webhook
POST wrote a complete Slack token into alerts.error and printed it to stdout,
where Fly retains it. Verified against real httpx before this existed.
"""

from app.redact import redact

SLACK = "https://hooks.slack.invalid/services/T04ABCDEFGH/B07ZYXWVUTS/aBcDeFgHiJkLmNoPqRsTuVwX"
DISCORD = "https://discord.invalid/api/webhooks/1234567890123456789/abcXYZ_-tokenmaterialhere012345"


def test_slack_webhook_token_is_masked():
    out = redact(f"Client error '404 Not Found' for url '{SLACK}'")
    assert "aBcDeFgHiJkLmNoPqRsTuVwX" not in out


def test_the_useful_part_of_a_slack_url_survives():
    """Redaction has to leave enough to debug with, or people turn it off."""
    out = redact(f"failed for url '{SLACK}'")
    assert "hooks.slack.invalid" in out, "host identifies which integration broke"
    assert "T04ABCDEFGH" in out, "team id is not secret and pinpoints the workspace"
    assert "***" in out, "the token is replaced, not merely deleted"


def test_discord_webhook_token_is_masked():
    out = redact(f"POST {DISCORD} failed")
    assert "abcXYZ_-tokenmaterialhere012345" not in out
    assert "discord.invalid" in out


def test_anthropic_key_is_masked():
    out = redact("auth error with key sk-ant-api03-AbCdEf1234567890GhIjKlMnOpQrStUvWxYz")
    assert "AbCdEf1234567890GhIjKlMnOpQrStUvWxYz" not in out
    assert "sk-ant-" in out, "prefix is useful for identifying which credential failed"


def test_serpapi_key_is_masked():
    key = "a" * 64
    out = redact(f"SerpApi 401 for api_key={key}")
    assert key not in out


def test_query_string_secrets_are_masked():
    out = redact("GET https://serpapi.com/search.json?engine=google&api_key=deadbeefcafe1234&q=coffee")
    assert "deadbeefcafe1234" not in out
    assert "engine=google" in out, "non-secret parameters should stay readable"


def test_ordinary_text_is_untouched():
    msg = "collect failed: connection reset by peer after 3 retries"
    assert redact(msg) == msg


def test_none_and_empty_are_safe():
    assert redact(None) == ""
    assert redact("") == ""
