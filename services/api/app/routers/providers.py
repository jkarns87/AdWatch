"""Provider key health, workspace-scoped.

Deliberately not folded into /health: the container HEALTHCHECK polls that every 15
seconds, and putting an outbound SerpApi call there would mean ~5,760 requests a day
and would make container liveness depend on SerpApi's uptime.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import providers as prov
from ..auth import current_workspace_id
from ..config import get_settings
from ..db import get_db

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/serpapi", summary="Is the SerpApi key valid, and how much quota is left?")
def serpapi(db: Session = Depends(get_db), workspace_id: int = Depends(current_workspace_id)):
    """status: ok | invalid | exhausted | unset | unreachable.

    `invalid` and `unreachable` are kept distinct because the operator response differs —
    one is a bad key, the other is SerpApi being down.
    """
    return prov.serpapi_status(db, workspace_id=workspace_id, platform_key=get_settings().serpapi_api_key)
