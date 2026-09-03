"""Per-workspace API keys: stored encrypted, resolved with a platform fallback."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app import crypto
from app import models as m
from app import workspace_secrets as sec

SERPAPI_KEY = "f" * 64
ANTHROPIC_KEY = "sk-ant-api03-workspace-owned-key"


@pytest.fixture(autouse=True)
def keyed(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    yield
    crypto._fernet = None


def test_set_then_get_roundtrips(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    assert sec.get_secret(db, workspace_id=1, kind="serpapi") == SERPAPI_KEY


def test_the_stored_column_is_ciphertext_not_the_key(db):
    """The whole point: someone reading the table gets nothing usable."""
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    row = db.scalars(select(m.WorkspaceSecret)).one()
    assert SERPAPI_KEY not in row.ciphertext
    assert row.ciphertext != SERPAPI_KEY


def test_only_the_last_four_characters_are_kept_in_clear(db):
    sec.set_secret(db, workspace_id=1, kind="anthropic", plaintext=ANTHROPIC_KEY)
    row = db.scalars(select(m.WorkspaceSecret)).one()
    assert row.last4 == "-key"


def test_setting_twice_replaces_rather_than_duplicating(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext="a" * 64)
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext="b" * 64)
    rows = db.scalars(select(m.WorkspaceSecret).where(m.WorkspaceSecret.workspace_id == 1)).all()
    assert len(rows) == 1
    assert sec.get_secret(db, workspace_id=1, kind="serpapi") == "b" * 64


def test_listing_never_exposes_plaintext(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    listed = sec.list_secrets(db, workspace_id=1)
    assert listed[0]["kind"] == "serpapi"
    assert listed[0]["last4"] == "ffff"
    assert SERPAPI_KEY not in str(listed)
    assert "ciphertext" not in str(listed), "ciphertext has no business leaving the API either"


def test_one_workspace_cannot_read_another(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    assert sec.get_secret(db, workspace_id=2, kind="serpapi") is None


def test_delete_removes_it(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    sec.delete_secret(db, workspace_id=1, kind="serpapi")
    assert sec.get_secret(db, workspace_id=1, kind="serpapi") is None


def test_resolve_prefers_the_workspace_key(db):
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    assert sec.resolve_key(db, workspace_id=1, kind="serpapi", fallback="platform-key") == SERPAPI_KEY


def test_resolve_falls_back_to_the_platform_key(db):
    assert sec.resolve_key(db, workspace_id=1, kind="serpapi", fallback="platform-key") == "platform-key"


def test_resolve_returns_empty_when_neither_exists(db):
    assert sec.resolve_key(db, workspace_id=1, kind="serpapi", fallback="") == ""


def test_unreadable_ciphertext_falls_back_rather_than_crashing_a_run(db, monkeypatch):
    """After a botched key rotation the row cannot be decrypted. A collect run
    should degrade to the platform key, not 500."""
    sec.set_secret(db, workspace_id=1, kind="serpapi", plaintext=SERPAPI_KEY)
    crypto._fernet = None
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert sec.resolve_key(db, workspace_id=1, kind="serpapi", fallback="platform-key") == "platform-key"
