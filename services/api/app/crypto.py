"""Encryption envelope for customer-supplied API keys.

`SECRET_ENCRYPTION_KEY` holds one or more urlsafe-base64 Fernet keys, comma
separated. The first encrypts; every listed key can decrypt. That ordering is
what makes rotation possible: prepend a new key, let writes migrate naturally,
drop the old one once nothing decrypts with it any more.

Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Threat model — narrow on purpose. This protects ciphertext at rest: a leaked
pg_dump, a backup, a snapshot, read-only SQL injection, anyone with psql. It
does NOT protect against full host compromise, because the running process must
be able to decrypt. Anything stronger needs an HSM or an external KMS holding
the key out of the app's reach.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class EncryptionUnavailable(RuntimeError):
    """No usable SECRET_ENCRYPTION_KEY. Never fall back to storing plaintext."""


class DecryptionError(RuntimeError):
    """Ciphertext could not be read with any configured key."""


_fernet: MultiFernet | None = None


def _keys() -> list[str]:
    raw = os.environ.get("SECRET_ENCRYPTION_KEY", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def _cipher() -> MultiFernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    keys = _keys()
    if not keys:
        raise EncryptionUnavailable(
            "SECRET_ENCRYPTION_KEY is not set; refusing to handle customer credentials"
        )
    try:
        _fernet = MultiFernet([Fernet(k.encode()) for k in keys])
    except (ValueError, TypeError) as e:
        raise EncryptionUnavailable(f"SECRET_ENCRYPTION_KEY is not a valid Fernet key: {e}") from e
    return _fernet


def available() -> bool:
    """True when secrets can be stored. Lets callers degrade to platform keys
    rather than crashing a request."""
    try:
        _cipher()
        return True
    except EncryptionUnavailable:
        return False


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise DecryptionError("ciphertext is not readable with any configured key") from e


def last4(plaintext: str) -> str:
    """The only part of a credential that may be shown back to a user."""
    return plaintext[-4:] if plaintext else ""
