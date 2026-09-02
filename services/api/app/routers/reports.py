"""Report generator: one call, one file, tailored to the reader.

GET /watchlists/{id}/report?audience=cfo|marketing&format=pdf|docx|md&days=7
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .. import models as m
from ..auth import get_watchlist
from ..db import get_db
from ..reports.data import build_report_data
from ..reports.render_docx import render_docx
from ..reports.render_md import render_md
from ..reports.render_pdf import render_pdf

router = APIRouter(prefix="/watchlists", tags=["reports"])

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown; charset=utf-8",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "watchlist"


@router.get("/{watchlist_id}/report")
def report(
    audience: Literal["cfo", "marketing"] = Query(default="marketing"),
    format: Literal["pdf", "docx", "md"] = Query(default="pdf"),  # noqa: A002
    days: int = Query(default=7, ge=1, le=90),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    data = build_report_data(db, w, audience=audience, days=days)
    if format == "pdf":
        body: bytes | str = render_pdf(data)
    elif format == "docx":
        body = render_docx(data)
    else:
        body = render_md(data)
    fname = f"adwatch-{_slug(w.name)}-{audience}-{datetime.now(UTC).date().isoformat()}.{format}"
    return Response(
        content=body,
        media_type=MIME[format],
        headers={"Content-Disposition": f'attachment; filename="{fname}"', "X-Report-Model": str(data["executive_summary"].get("model", ""))},
    )


@router.get("/{watchlist_id}/report/data")
def report_data(
    audience: Literal["cfo", "marketing"] = Query(default="marketing"),
    days: int = Query(default=7, ge=1, le=90),
    w: m.Watchlist = Depends(get_watchlist),
    db: Session = Depends(get_db),
):
    """The assembled report payload as JSON (handy for the frontend preview and for tests)."""
    return build_report_data(db, w, audience=audience, days=days)
