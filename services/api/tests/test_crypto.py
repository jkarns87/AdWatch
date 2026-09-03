"""Envelope for customer-supplied API keys.

Threat model, deliberately narrow: this defends against database compromise —
a leaked pg_dump, a backup, a snapshot, read-only SQL injection, someone with
psql. It does NOT defend against full host compromise, because the process has
to be able to decrypt. See docs/SECRETS.md.
"""

import pytest
from cryptography.fernet import Fernet

from app import crypto


@pytest.fixture
def keyed(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto, "_fernet", None)  # drop any cached instance
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", key)
    yield key
    crypto._fernet = None


def test_roundtrip(keyed):
    assert crypto.decrypt(crypto.encrypt("sk-ant-secret-value")) == "sk-ant-secret-value"


def test_ciphertext_does_not_contain_the_plaintext(keyed):
    token = crypto.encrypt("a" * 64)
    assert "a" * 64 not in token


def test_same_plaintext_encrypts_differently_each_time(keyed):
    """Fernet includes a random IV, so identical keys must not produce identical
    ciphertext — otherwise the table leaks which workspaces share a key."""
    assert crypto.encrypt("same") != crypto.encrypt("same")


def test_a_token_from_another_key_cannot_be_read(keyed, monkeypatch):
    token = crypto.encrypt("secret")
    crypto._fernet = None
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)


def test_missing_key_fails_loudly_rather_than_storing_plaintext(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(crypto.EncryptionUnavailable):
        crypto.encrypt("secret")
    crypto._fernet = None


def test_rotation_reads_tokens_written_under_the_previous_key(monkeypatch):
    """SECRET_ENCRYPTION_KEY takes a comma-separated list: the first encrypts,
    all of them decrypt. That is what makes key rotation possible without a
    migration that decrypts every row at once."""
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()

    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", old)
    legacy_token = crypto.encrypt("written-under-the-old-key")

    crypto._fernet = None
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", f"{new},{old}")
    assert crypto.decrypt(legacy_token) == "written-under-the-old-key"
    # and new writes use the new key, unreadable by the old one alone
    fresh = crypto.encrypt("written-under-the-new-key")
    crypto._fernet = None
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", old)
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(fresh)
    crypto._fernet = None


def test_last4_is_derived_from_plaintext_for_display(keyed):
    assert crypto.last4("sk-ant-api03-abcdef1234") == "1234"
    assert crypto.last4("abc") == "abc"
    assert crypto.last4("") == ""
