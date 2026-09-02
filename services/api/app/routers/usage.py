"""Usage & budget: SerpApi searches consumed this month per workspace, projections, and the plan catalog.

The workspace's *plan* lives in the Xano control plane (workspace.plan). When AUTH_PROVIDER=xano the
plan comes back with token introspection; with AUTH_PROVIDER=none we assume "team" so the demo isn't gated.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..auth import current_plan, current_workspace_id
from ..db import get_db
from ..metering import cost_by_watchlist, summarize
from ..plans import CURRENT_CADENCE, PLANS, RATE_PER_SEARCH_USD, cost_usd, plan_dict, searches_per_month, searches_per_run

router = APIRouter(prefix="/usage", tags=["usage"])


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=s.UsageOut)
def usage(
    db: Session = Depends(get_db),
    workspace_id: int = Depends(current_workspace_id),
    plan_key: str = Depends(current_plan),
):
    now = datetime.now(UTC)
    start = _month_start(now)
    plan = PLANS.get(plan_key, PLANS["team"])

    llm = summarize(db, workspace_id=workspace_id, since=start)
    llm_by_watchlist = cost_by_watchlist(db, workspace_id=workspace_id, since=start)

    watchlists = db.scalars(select(m.Watchlist).where(m.Watchlist.workspace_id == workspace_id).order_by(m.Watchlist.id)).all()
    rows: list[s.WatchlistUsage] = []
    total_searches = 0
    total_runs = 0
    projected_current = 0
    projected_plan = 0
    for w in watchlists:
        used, runs, last = db.execute(
            select(func.coalesce(func.sum(m.Run.searches_used), 0), func.count(m.Run.id), func.max(m.Run.finished_at)).where(
                m.Run.watchlist_id == w.id, m.Run.started_at >= start
            )
        ).one()
        c, k = len(w.competitors), len(w.keywords)
        per_run = searches_per_run(c, k)
        cur = searches_per_month(c, k, CURRENT_CADENCE, batch_trends=False)
        opt = searches_per_month(c, k, plan.cadence, batch_trends=True)
        total_searches += int(used)
        total_runs += int(runs)
        projected_current += cur
        projected_plan += opt
        rows.append(
            s.WatchlistUsage(
                watchlist_id=w.id,
                name=w.name,
                competitors=c,
                keywords=k,
                searches_used=int(used),
                runs=int(runs),
                last_run_at=last,
                searches_per_run=per_run,
                projected_month_current=cur,
                projected_month_plan=opt,
                over_plan_limits=(c > plan.competitors_per_watchlist or k > plan.keywords_per_watchlist),
                llm_cost_usd=llm_by_watchlist.get(w.id, 0.0),
            )
        )

    return s.UsageOut(
        workspace_id=workspace_id,
        plan=plan_key if plan_key in PLANS else "team",
        period_start=start,
        period_end=now,
        searches_used=total_searches,
        searches_budget=plan.searches_per_month,
        searches_remaining=max(plan.searches_per_month - total_searches, 0),
        budget_used_pct=round(min(total_searches / plan.searches_per_month, 1.0) * 100, 1) if plan.searches_per_month else 0.0,
        runs=total_runs,
        cost_to_date_usd=cost_usd(total_searches),
        projected_month_current_cadence=projected_current,
        projected_month_plan_cadence=projected_plan,
        projected_cost_current_usd=cost_usd(projected_current),
        projected_cost_plan_usd=cost_usd(projected_plan),
        rate_per_search_usd=RATE_PER_SEARCH_USD,
        watchlists_used=len(watchlists),
        watchlists_limit=plan.watchlists,
        by_watchlist=rows,
        plans=[plan_dict(p) for p in PLANS.values()],
        llm=s.LlmUsage(**llm),
        total_cost_usd=round(cost_usd(total_searches) + llm["cost_usd"], 6),
    )
