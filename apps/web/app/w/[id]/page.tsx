"use client";

import { use, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Change, Creative, Insight, SerpOut, TrendsOut, WatchlistDetail } from "@/lib/types";
import { fmtTime } from "@/components/Badges";
import { ChangeRow } from "@/components/ChangeRow";
import { InsightCard } from "@/components/InsightCard";
import { CreativeCard } from "@/components/CreativeCard";
import { SerpTable } from "@/components/SerpTable";
import { TrendSparkline } from "@/components/TrendSparkline";
import { ExportMenu } from "@/components/ExportMenu";

type Tab = "insights" | "changes" | "competitors" | "keywords";

export default function WatchlistPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idStr } = use(params);
  const id = Number(idStr);

  const [w, setW] = useState<WatchlistDetail | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [serp, setSerp] = useState<SerpOut | null>(null);
  const [trends, setTrends] = useState<TrendsOut | null>(null);
  const [kwId, setKwId] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("insights");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newComp, setNewComp] = useState({ name: "", domain: "" });
  const [newKw, setNewKw] = useState("");

  const load = useCallback(async () => {
    try {
      const [d, ins, ch, cr] = await Promise.all([api.watchlist(id), api.insights(id), api.changes(id, 100), api.creatives(id)]);
      setW(d); setInsights(ins); setChanges(ch); setCreatives(cr);
      if (kwId === null && d.keywords.length) setKwId(d.keywords[0].id);
    } catch (e: any) { setErr(String(e.message ?? e)); }
  }, [id, kwId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (kwId === null) return;
    api.serp(id, kwId).then(setSerp).catch(() => setSerp(null));
    api.trends(id, kwId).then(setTrends).catch(() => setTrends(null));
  }, [id, kwId]);

  const collect = async () => {
    setBusy(true); setStatus("collecting live data via SerpApi…"); setErr(null);
    try {
      const r = await api.collectAndAnalyze(id);
      setStatus(`run #${r.run.id}: ${r.snapshots} snapshots, ${r.changes.length} changes, ${r.insights.length} insights, ${r.alerts_sent} alert${r.alerts_sent === 1 ? "" : "s"} sent`);
      await load();
      setTab(r.insights.length ? "insights" : "changes");
    } catch (e: any) { setErr(String(e.message ?? e)); setStatus(null); }
    finally { setBusy(false); }
  };

  const addComp = async () => {
    const domain = newComp.domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
    if (domain.length < 4) return;
    try { await api.addCompetitor(id, { name: newComp.name.trim() || domain.split(".")[0], domain }); setNewComp({ name: "", domain: "" }); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
  };
  const addKw = async () => {
    if (!newKw.trim()) return;
    try { await api.addKeyword(id, newKw.trim()); setNewKw(""); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
  };

  if (err && !w) return <div className="panel p-4" style={{ color: "var(--high)" }}>{err}</div>;
  if (!w) return <div className="muted">loading…</div>;

  const lastRunId = w.last_run?.id ?? 0;
  const newIds = new Set(changes.filter((c) => c.kind === "creative_launched" && c.run_id === lastRunId).map((c) => String((c.payload as any).creative_id)));

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{w.name}</h1>
          <div className="muted text-sm mt-1">
            {w.vertical} · {w.geo}{w.location ? ` · ${w.location}` : ""} · {w.competitors.length} competitors · {w.keywords.length} keywords · last run {fmtTime(w.last_run?.finished_at)}{w.last_run ? ` (${w.last_run.searches_used} searches)` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu watchlistId={id} />
          <button className="btn btn-primary" onClick={collect} disabled={busy}>{busy ? "Collecting…" : "Collect now"}</button>
        </div>
      </div>
      {status && <div className="panel-2 p-2 mt-3 text-sm">{status}</div>}
      {err && <div className="panel p-2 mt-3 text-sm" style={{ color: "var(--high)" }}>{err}</div>}

      <nav className="flex gap-1 mt-5 border-b" style={{ borderColor: "var(--line)" }}>
        {(["insights", "changes", "competitors", "keywords"] as Tab[]).map((t) => (
          <button key={t} className="tab text-sm capitalize" data-active={tab === t} onClick={() => setTab(t)}>
            {t}{t === "insights" ? ` (${insights.length})` : t === "changes" ? ` (${changes.length})` : ""}
          </button>
        ))}
      </nav>

      {tab === "insights" && (
        <div className="grid gap-4 mt-4 lg:grid-cols-2">
          {insights.length === 0 && <div className="muted">No insights yet — run Collect twice (first run is the baseline).</div>}
          {insights.map((i) => <InsightCard key={i.id} i={i} />)}
        </div>
      )}

      {tab === "changes" && (
        <div className="panel p-4 mt-4 divide-y" style={{ borderColor: "var(--line)" }}>
          {changes.length === 0 && <div className="muted">No changes detected yet.</div>}
          {changes.map((c) => <ChangeRow key={c.id} c={c} />)}
        </div>
      )}

      {tab === "competitors" && (
        <div className="mt-4 space-y-6">
          <div className="panel-2 p-3 flex flex-wrap gap-2 items-center">
            <span className="muted text-xs">Add competitor</span>
            <input className="panel-2 p-1.5 text-sm" placeholder="Name (optional)" value={newComp.name} onChange={(e) => setNewComp({ ...newComp, name: e.target.value })} />
            <input className="panel-2 p-1.5 text-sm flex-1 min-w-[200px]" placeholder="competitor-domain.com" value={newComp.domain} onChange={(e) => setNewComp({ ...newComp, domain: e.target.value })} onKeyDown={(e) => e.key === "Enter" && addComp()} />
            <button className="btn text-sm" onClick={addComp}>Add</button>
          </div>
          {w.competitors.map((c) => {
            const mine = creatives.filter((x) => x.competitor_id === c.id);
            return (
              <section key={c.id}>
                <div className="flex items-baseline gap-3">
                  <h2 className="font-medium text-lg">{c.name}</h2>
                  <span className="muted text-sm">{c.domain} · {c.active_creatives} active creatives</span>
                </div>
                <div className="grid gap-3 mt-2 sm:grid-cols-2 lg:grid-cols-4">
                  {mine.slice(0, 12).map((cr) => <CreativeCard key={cr.id} c={cr} isNew={newIds.has(cr.creative_id)} />)}
                  {mine.length === 0 && <div className="muted text-sm">no creatives captured yet</div>}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {tab === "keywords" && (
        <div className="mt-4">
          <div className="panel-2 p-3 flex flex-wrap gap-2 items-center mb-3">
            <span className="muted text-xs">Add keyword</span>
            <input className="panel-2 p-1.5 text-sm flex-1 min-w-[200px]" placeholder="e.g. cold brew delivery" value={newKw} onChange={(e) => setNewKw(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addKw()} />
            <button className="btn text-sm" onClick={addKw}>Add</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {w.keywords.map((k) => (
              <button key={k.id} className="btn" style={kwId === k.id ? { borderColor: "var(--accent)" } : {}} onClick={() => setKwId(k.id)}>{k.term}</button>
            ))}
          </div>
          <div className="grid gap-4 mt-4 lg:grid-cols-2">
            {serp && <SerpTable s={serp} />}
            {trends && <TrendSparkline t={trends} />}
          </div>
        </div>
      )}
    </div>
  );
}
