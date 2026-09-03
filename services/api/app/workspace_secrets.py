"""Per-workspace API keys: the only module that reads workspace_secrets.ciphertext.

Keeping decryption in one place is deliberate. A key that is decrypted in three
routers is a key that eventually gets logged in one of them.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crypto
from . import models as m

log = logging.getLogger(__name__)

KINDS = ("serpapi", "anthropic")


def set_secret(db: Session, *, workspace_id: int, kind: str, plaintext: str) -> m.WorkspaceSecret:
    """Store or replace one workspace's key. Raises EncryptionUnavailable rather
    than degrading to plaintext if no encryption key is configured."""
    if kind not in KINDS:
        raise ValueError(f"unknown secret kind {kind!r}")
    row = db.scalar(
        select(m.WorkspaceSecret).where(
            m.WorkspaceSecret.workspace_id == workspace_id, m.WorkspaceSecret.kind == kind
        )
    )
    ciphertext, tail = crypto.encrypt(plaintext), crypto.last4(plaintext)
    if row is None:
        row = m.WorkspaceSecret(workspace_id=workspace_id, kind=kind, ciphertext=ciphertext, last4=tail)
        db.add(row)
    else:
        row.ciphertext, row.last4 = ciphertext, tail
    db.flush()
    return row


def get_secret(db: Session, *, workspace_id: int, kind: str) -> str | None:
    """Decrypted key, or None when absent or unreadable."""
    row = db.scalar(
        select(m.WorkspaceSecret).where(
            m.WorkspaceSecret.workspace_id == workspace_id, m.WorkspaceSecret.kind == kind
        )
    )
    if row is None:
        return None
    try:
        return crypto.decrypt(row.ciphertext)
    except (crypto.DecryptionError, crypto.EncryptionUnavailable):
        # Typically a half-finished key rotation. Say which row, never the contents.
        log.error("workspace %s %s secret is unreadable with the configured key", workspace_id, kind)
        return None


def delete_secret(db: Session, *, workspace_id: int, kind: str) -> None:
    row = db.scalar(
        select(m.WorkspaceSecret).where(
            m.WorkspaceSecret.workspace_id == workspace_id, m.WorkspaceSecret.kind == kind
        )
    )
    if row is not None:
        db.delete(row)
        db.flush()


def list_secrets(db: Session, *, workspace_id: int) -> list[dict[str, Any]]:
    """Safe for an API response: kind, last4 and timestamps only."""
    rows = db.scalars(
        select(m.WorkspaceSecret)
        .where(m.WorkspaceSecret.workspace_id == workspace_id)
        .order_by(m.WorkspaceSecret.kind)
    ).all()
    return [
        {"kind": r.kind, "last4": r.last4, "created_at": r.created_at, "updated_at": r.updated_at}
        for r in rows
    ]


def resolve_key(db: Session, *, workspace_id: int, kind: str, fallback: str = "") -> str:
    """The workspace's own key when it has one, otherwise the platform key.

    Falls back rather than raising on an unreadable row: a botched rotation should
    degrade a run to platform quota, not 500 every collect in the workspace.
    """
    return get_secret(db, workspace_id=workspace_id, kind=kind) or fallback
