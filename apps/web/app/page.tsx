"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtTime } from "@/components/Badges";
import type { AlertFeedItem, SerpApiStatus, UsageOut } from "@/lib/types";

const usd = (n: number) => `$${n.toFixed(2)}`;
const num = (n: number | null | undefined) => (n ?? 0).toLocaleString();

/** SerpApi key health. `invalid` and `unreachable` are different problems: a bad key
 *  versus SerpApi being down, and the operator response differs. */
const KEY_STATE: Record<string, { label: string; tone: string; hint: string }> = {
  ok: { label: "Valid", tone: "low", hint: "key accepted, quota remaining" },
  exhausted: { label: "Exhausted", tone: "high", hint: "key is valid but every search is spent" },
  invalid: { label: "Invalid", tone: "high", hint: "SerpApi rejected this key — collection will 502" },
  unset: { label: "Not set", tone: "medium", hint: "no key on the workspace or the platform" },
  unreachable: { label: "Unreachable", tone: "medium", hint: "SerpApi did not answer — not necessarily a bad key" },
};

/** Granted credits sit on top of the plan allowance, so "14,370 of 250/month" is
 *  nonsense. Say which is which. */
function quotaSub(s: SerpApiStatus | null): string | undefined {
  if (!s) return undefined;
  if (s.extra_credits) return `${num(s.plan_searches_left)} plan + ${num(s.extra_credits)} credits`;
  if (s.searches_per_month) return `of ${num(s.searches_per_month)}/month`;
  return undefined;
}

/** An unpriced model records tokens but no cost, so the total is an understatement
 *  rather than a real figure. Say so instead of showing a confident number. */
function claudeSub(llm: UsageOut["llm"] | undefined): string | undefined {
  if (!llm) return undefined;
  if (llm.unpriced_calls > 0) return `${num(llm.unpriced_calls)} unpriced — cost understated`;
  return `${num(llm.input_tokens + llm.output_tokens)} tokens`;
}

function Stat({ label, value, sub, tone }: Readonly<{ label: string; value: string; sub?: string; tone?: string }>) {
  return (
    <div className="panel p-4" data-testid="kpi">
      <div className="muted text-xs uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1" style={{ color: tone ? `var(--${tone})` : "var(--text)" }}>
        {value}
      </div>
      {sub && <div className="muted text-xs mt-1">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [usage, setUsage] = useState<UsageOut | null>(null);
  const [serp, setSerp] = useState<SerpApiStatus | null>(null);
  const [alerts, setAlerts] = useState<AlertFeedItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    // Settled independently: a failing provider check should not blank the spend
    // panels, and vice versa.
    api.usage().then(setUsage).catch((e) => setErr(String(e.message ?? e)));
    api.serpapiStatus().then(setSerp).catch(() => setSerp(null));
    api.alertFeed(6).then(setAlerts).catch(() => setAlerts([]));
  }, []);

  const llm = usage?.llm;
  const key = serp ? (KEY_STATE[serp.status] ?? KEY_STATE.unreachable) : null;

  return (
    <div>
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="muted text-sm mt-1">
            What the sensors cost and whether they are working. Spend is this calendar month.
          </p>
        </div>
        <Link href="/watchlists" className="btn">All watchlists</Link>
      </div>

      {err && (
        <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>
          API error: {err}
        </div>
      )}

      {/* ---- KPI strip ------------------------------------------------------------ */}
      <div className="grid gap-3 mt-5 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="SerpApi searches left"
          value={serp?.searches_left != null ? num(serp.searches_left) : "—"}
          sub={quotaSub(serp)}
          tone={serp?.status === "exhausted" ? "high" : undefined}
        />
        <Stat
          label="Cost this month"
          value={usage ? usd(usage.total_cost_usd) : "—"}
          sub={usage ? `${usd(usage.cost_to_date_usd)} SerpApi · ${usd(llm?.cost_usd ?? 0)} Claude` : undefined}
        />
        <Stat
          label="Claude calls"
          value={llm ? num(llm.calls) : "—"}
          sub={claudeSub(llm)}
          tone={llm && llm.unpriced_calls > 0 ? "medium" : undefined}
        />
        <Stat
          label="Watchlists"
          value={usage ? `${usage.watchlists_used} / ${usage.watchlists_limit}` : "—"}
          sub={usage ? `${usage.runs} runs this month` : undefined}
        />
      </div>

      {/* ---- key health ----------------------------------------------------------- */}
      <section className="grid gap-3 mt-3 lg:grid-cols-2">
        <div className="panel p-4" data-testid="provider-serpapi">
          <div className="flex items-center justify-between">
            <div className="font-medium">SerpApi key</div>
            {key && <span className={`badge sev-${key.tone}`}>{key.label}</span>}
          </div>
          <div className="muted text-sm mt-2">{key?.hint ?? "checking…"}</div>
          {serp && (
            <div className="muted text-xs mt-3">
              {serp.plan ?? "unknown plan"} · key from {serp.key_source}
              {serp.cached && " · cached"}
            </div>
          )}
        </div>

        <div className="panel p-4" data-testid="provider-anthropic">
          <div className="flex items-center justify-between">
            <div className="font-medium">Claude</div>
            {llm && (
              <span className={`badge ${llm.unpriced_calls > 0 ? "sev-medium" : "sev-low"}`}>
                {llm.unpriced_calls > 0 ? "Unpriced model" : "Metered"}
              </span>
            )}
          </div>
          <div className="muted text-sm mt-2">
            {llm?.by_model.length
              ? llm.by_model.map((m) => `${m.model} (${num(m.calls)})`).join(", ")
              : "no calls recorded yet"}
          </div>
          <div className="muted text-xs mt-3">
            {llm?.metering_since ? `metering since ${fmtTime(llm.metering_since)}` : "metering has not started"}
          </div>
        </div>
      </section>

      {/* ---- alert cards ---------------------------------------------------------- */}
      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-lg">Recent alerts</h2>
          <Link href="/alerts" className="muted text-sm">All alerts →</Link>
        </div>
        {alerts === null && <div className="muted text-sm mt-2">loading…</div>}
        {alerts?.length === 0 && (
          <div className="panel p-5 mt-2 muted text-sm">
            Nothing yet. Run a collection on a watchlist and the second run starts producing changes.
          </div>
        )}
        <div className="grid gap-3 mt-3 md:grid-cols-2">
          {alerts?.map((a) => (
            <Link key={a.id} href={`/watchlists/${a.watchlist_id}`} className="panel p-4 block" style={{ color: "var(--text)" }}>
              <div className="flex items-center justify-between gap-2">
                <span className={`badge sev-${a.severity}`}>{a.severity}</span>
                <span className="muted text-xs">{fmtTime(a.created_at)}</span>
              </div>
              <div className="font-medium mt-2">{a.watchlist_name}</div>
              <div className="muted text-sm mt-1">{a.summary}</div>
              <div className="muted text-xs mt-3">
                {a.delivery
                  ? `${a.delivery.channel} · ${a.delivery.status}`
                  : "not dispatched — below the alert threshold"}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ---- burn by watchlist ---------------------------------------------------- */}
      <section className="mt-8">
        <h2 className="font-medium text-lg">Where the money goes</h2>
        <div className="panel mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="muted text-xs uppercase tracking-wide">
              <tr className="text-left">
                <th className="p-3">Watchlist</th>
                <th className="p-3 text-right">Searches</th>
                <th className="p-3 text-right">SerpApi</th>
                <th className="p-3 text-right">Claude</th>
                <th className="p-3 text-right">Total</th>
                <th className="p-3">Last run</th>
              </tr>
            </thead>
            <tbody>
              {!usage?.by_watchlist.length && (
                <tr>
                  <td colSpan={6} className="p-4 muted">No watchlists yet.</td>
                </tr>
              )}
              {usage?.by_watchlist.map((w) => {
                const serpCost = w.searches_used * usage.rate_per_search_usd;
                return (
                  <tr key={w.watchlist_id} className="border-t" style={{ borderColor: "var(--line)" }}>
                    <td className="p-3">
                      <Link href={`/watchlists/${w.watchlist_id}`}>{w.name}</Link>
                    </td>
                    <td className="p-3 text-right">{num(w.searches_used)}</td>
                    <td className="p-3 text-right muted">{usd(serpCost)}</td>
                    <td className="p-3 text-right muted">{usd(w.llm_cost_usd)}</td>
                    <td className="p-3 text-right">{usd(serpCost + w.llm_cost_usd)}</td>
                    <td className="p-3 muted">{fmtTime(w.last_run_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
