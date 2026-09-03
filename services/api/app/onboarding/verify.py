"""Check a proposed competitor against the Ads Transparency Center before persisting it.

Claude proposes plausible companies; plausible is not the same as advertising. A domain
that buys no ads costs a SerpApi search on every run, forever, and sits in the UI looking
entirely legitimate. One search now is cheaper than that.
"""

from __future__ import annotations

import logging
from typing import Any

from ..collectors.serpapi_client import SerpApiClient

log = logging.getLogger(__name__)


def domain_advertises(client: SerpApiClient, domain: str) -> bool:
    """True when the Ads Transparency Center knows this domain as an advertiser.

    Raises on transport failure rather than returning False: "SerpApi is down" and
    "this company buys no ads" are different answers and the caller reports them
    differently.
    """
    res = client.ads_transparency(domain=domain, num=1)
    data: dict[str, Any] = res.data or {}
    if data.get("ad_creatives"):
        return True
    advertiser = data.get("advertiser")
    if isinstance(advertiser, dict) and advertiser.get("id"):
        return True
    if isinstance(advertiser, list) and advertiser:
        return True
    return False
