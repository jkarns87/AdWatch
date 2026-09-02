"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { xano, xanoEnabled } from "@/lib/xano";
import type { PlanInfo, PlanKey, UsageOut, XanoMe } from "@/lib/types";
import { fmtTime } from "@/components/Badges";

const usd = (n: number) => `$${n.toFixed(2)}`;
const num = (n: number) => n.toLocaleString();

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "high" | "medium" | "low" }) {
  return (
    <div className="panel p-4">
      <div className="muted text-xs uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1" style={tone ? { color: `var(--${tone})` } : {}}>{value}</div>
      {sub && <div className="muted text-xs mt-1">{sub}</div>}
    </div>
  );
}

function cadenceLine(p: PlanInfo): string {
  const c = p.cadence;
  return `creatives ${c.creatives_per_day}×/day · SERP ${c.serp_per_day}×/day · demand ${c.trends_per_day}×/day · related queries ${c.related_per_week}×/wk`;
}

export default function UsagePage() {
  const [u, setU] = useState<UsageOut | null>(null);
  const [me, setMe] = useState<XanoMe | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<PlanKey | null>(null);

  const load = useCallback(async () => {
    try {
      const [usage, who] = await Promise.all([api.usage(), xanoEnabled ? xano.me().catch(() => null) : Promise.resolve(null)]);
      setU(usage); setMe(who);
    } catch (e: any) { setErr(String(e.message ?? e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const switchPlan = async (plan: PlanKey) => {
    setBusy(plan); setErr(null);
    try {
      await xano.setPlan(plan);
      // the API caches token introspection for 5 min; reload shows the new limits immediately from the plan catalog
      await load();
      window.dispatchEvent(new Event("adwatch:alerts-changed"));
    } catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(null); }
  };

  if (err && !u) return <div className="panel p-4" style={{ color: "var(--high)" }}>{err}</div>;
  if (!u) return <div className="muted">loading…</div>;

  const planKey: PlanKey = me?.workspace.plan ?? u.plan;
  const plan = u.plans.find((p) => p.key === planKey) ?? u.plans[1];
  const budget = plan.searches_per_month;
  const usedPct = budget ? Math.min(100, Math.round((u.searches_used / budget) * 100)) : 0;
  const tone = usedPct >= 90 ? "high" : usedPct >= 70 ? "medium" : "low";
  const savings = u.projected_cost_current_usd - u.projected_cost_plan_usd;
  const canSwitch = xanoEnabled && me?.role === "owner";

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Usage &amp; plan</h1>
          <div className="muted text-sm mt-1">
            Every data pull is one search against the workspace budget · period {fmtTime(u.period_start)} → today · rate {usd(u.rate_per_search_usd)}/search
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="muted text-sm">current plan</span>
          <span className="badge kind text-sm" style={{ fontSize: 13 }}>{plan.name}</span>
        </div>
      </div>

      {err && <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>{err}</div>}

      <div className="grid gap-3 mt-5 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Searches this month" value={`${num(u.searches_used)} / ${num(budget)}`} sub={`${u.runs} collection run${u.runs === 1 ? "" : "s"}`} tone={tone} />
        <Stat label="Cost to date" value={usd(u.cost_to_date_usd)} sub="SerpApi searches × blended rate" />
        <Stat label="Projected / month" value={usd(u.projected_cost_plan_usd)} sub={`${num(u.projected_month_plan_cadence)} searches at ${plan.name} cadence`} />
        <Stat label="Watchlists" value={`${u.watchlists_used} / ${plan.watchlists}`} sub={`${plan.competitors_per_watchlist} competitors · ${plan.keywords_per_watchlist} keywords each`} />
      </div>

      <div className="panel p-4 mt-3">
        <div className="flex items-center justify-between text-sm">
          <span>Budget used</span>
          <span className="muted">{usedPct}% · {num(Math.max(budget - u.searches_used, 0))} searches left</span>
        </div>
        <div className="mt-2 h-2 rounded-full" style={{ background: "var(--panel-2)" }}>
          <div className="h-2 rounded-full" style={{ width: `${usedPct}%`, background: `var(--${tone})`, transition: "width .4s" }} />
        </div>
        <div className="muted text-xs mt-2">
          When the budget is exhausted the scheduler pauses collection for this workspace until the period resets — you never get a surprise bill, you get a nudge to upgrade.
        </div>
      </div>

      <section className="mt-8">
        <h2 className="font-medium text-lg">Where the searches go</h2>
        <div className="panel mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="muted text-xs uppercase tracking-wide">
              <tr className="text-left">
                <th className="p-3">Watchlist</th>
                <th className="p-3">Size</th>
                <th className="p-3 text-right">Per run</th>
                <th className="p-3 text-right">Used</th>
                <th className="p-3 text-right">Runs</th>
                <th className="p-3 text-right">Projected / mo</th>
                <th className="p-3">Last run</th>
              </tr>
            </thead>
            <tbody>
              {u.by_watchlist.length === 0 && (
                <tr><td colSpan={7} className="p-4 muted">No watchlists yet.</td></tr>
              )}
              {u.by_watchlist.map((w) => (
                <tr key={w.watchlist_id} className="border-t" style={{ borderColor: "var(--line)" }}>
                  <td className="p-3"><Link href={`/watchlists/${w.watchlist_id}`}>{w.name}</Link></td>
                  <td className="p-3 muted">
                    {w.competitors} competitors · {w.keywords} keywords
                    {w.over_plan_limits && <span className="badge sev-medium ml-2" title="exceeds plan limits">over plan</span>}
                  </td>
                  <td className="p-3 text-right">{w.searches_per_run}</td>
                  <td className="p-3 text-right">{num(w.searches_used)}</td>
                  <td className="p-3 text-right">{w.runs}</td>
                  <td className="p-3 text-right">{num(w.projected_month_plan)} <span className="muted">({usd(w.projected_month_plan * u.rate_per_search_usd)})</span></td>
                  <td className="p-3 muted">{fmtTime(w.last_run_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel-2 p-3 mt-2 text-sm">
          <span style={{ color: "var(--text)" }}>Budget guard.</span>{" "}
          <span className="muted">
            Naive cadence (everything every 6h) would cost {usd(u.projected_cost_current_usd)}/mo ({num(u.projected_month_current_cadence)} searches). Per-source cadence — {cadenceLine(plan)}, demand batched 5 keywords per call — brings it to {usd(u.projected_cost_plan_usd)}
            {savings > 0 ? <> and saves <span style={{ color: "var(--low)" }}>{usd(savings)}/mo</span></> : null} with the same alerts, because creatives change daily and demand moves weekly; only the paid SERP block moves by the hour.
          </span>
        </div>
      </section>

      <section className="mt-8">
        <div className="flex items-baseline justify-between">
          <h2 className="font-medium text-lg">Plans</h2>
          <span className="muted text-xs">{canSwitch ? "you own this workspace — switching is instant" : xanoEnabled ? "only the workspace owner can change the plan" : "plan changes require the Xano control plane"}</span>
        </div>
        <div className="grid gap-3 mt-2 md:grid-cols-3">
          {u.plans.map((p) => {
            const current = p.key === planKey;
            return (
              <div key={p.key} className="panel p-4 flex flex-col" style={current ? { borderColor: "var(--accent)" } : {}}>
                <div className="flex items-center justify-between">
                  <div className="font-medium text-lg">{p.name}</div>
                  <div className="text-lg">${p.price_usd}<span className="muted text-xs">/mo</span></div>
                </div>
                <div className="muted text-sm mt-1">{p.blurb}</div>
                <ul className="text-sm mt-3 space-y-1">
                  <li>{p.watchlists} watchlist{p.watchlists === 1 ? "" : "s"}</li>
                  <li>{p.competitors_per_watchlist} competitors · {p.keywords_per_watchlist} keywords each</li>
                  <li>{num(p.searches_per_month)} searches / month</li>
                  <li className="muted text-xs">{cadenceLine(p)}</li>
                </ul>
                <div className="mt-auto pt-4">
                  {current ? (
                    <span className="badge kind">current plan</span>
                  ) : (
                    <button className="btn w-full" disabled={!canSwitch || busy !== null} onClick={() => switchPlan(p.key)}>
                      {busy === p.key ? "…" : p.price_usd > plan.price_usd ? `Upgrade to ${p.name}` : `Switch to ${p.name}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
