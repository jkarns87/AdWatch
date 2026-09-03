"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BrandsOut, Change, Creative, Insight, SerpOut, TrendsOut, WatchlistDetail } from "@/lib/types";
import { fmtTime } from "@/components/Badges";
import { ChangeRow } from "@/components/ChangeRow";
import { InsightCard } from "@/components/InsightCard";
import { BrandDefenceTable } from "@/components/BrandDefenceTable";
import { CreativeCard } from "@/components/CreativeCard";
import { SerpTable } from "@/components/SerpTable";
import { TrendSparkline } from "@/components/TrendSparkline";
import { ExportMenu } from "@/components/ExportMenu";
import { DEFAULT_WINDOW_MONTHS, sortCreatives, withinMonths, type CreativeSortKey } from "@/lib/sortCreatives";

type Tab = "insights" | "changes" | "brands" | "competitors" | "keywords";

export default function WatchlistPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idStr } = use(params);
  const id = Number(idStr);
  const router = useRouter();

  const [w, setW] = useState<WatchlistDetail | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [serp, setSerp] = useState<SerpOut | null>(null);
  const [trends, setTrends] = useState<TrendsOut | null>(null);
  const [brands, setBrands] = useState<BrandsOut | null>(null);
  const [kwId, setKwId] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("insights");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newComp, setNewComp] = useState({ name: "", domain: "" });
  const [newKw, setNewKw] = useState("");
  const [sortKey, setSortKey] = useState<CreativeSortKey>("last_shown");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const load = useCallback(async () => {
    try {
      const [d, ins, ch, cr, br] = await Promise.all([
        api.watchlist(id), api.insights(id), api.changes(id, 100), api.creatives(id),
        api.brands(id).catch(() => null),
      ]);
      setW(d); setInsights(ins); setChanges(ch); setCreatives(cr); setBrands(br);
      // Pick a default keyword without reading kwId. Depending on it here recreated
      // `load`, which re-fired the effect below and fetched the whole page twice.
      setKwId((prev) => prev ?? d.keywords.find((k) => (k.kind ?? "keyword") === "keyword")?.id ?? null);
    } catch (e: any) { setErr(String(e.message ?? e)); }
  }, [id]);

  // The per-keyword panels (paid block, demand) are fetched separately from the rest
  // of the page, so they need refetching explicitly after a run. Leaving it to the
  // effect below meant a collect that did not change the selected keyword left the
  // SerpApi table showing the previous run's ads.
  const loadKeyword = useCallback(async (k: number | null) => {
    if (k === null) return;
    await Promise.all([
      api.serp(id, k).then(setSerp).catch(() => setSerp(null)),
      api.trends(id, k).then(setTrends).catch(() => setTrends(null)),
    ]);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => { loadKeyword(kwId); }, [loadKeyword, kwId]);

  const collect = async () => {
    setBusy(true); setStatus("collecting live data via SerpApi…"); setErr(null);
    try {
      const r = await api.collectAndAnalyze(id);
      setStatus(`run #${r.run.id}: ${r.snapshots} snapshots, ${r.changes.length} changes, ${r.insights.length} insights, ${r.alerts_sent} alert${r.alerts_sent === 1 ? "" : "s"} sent`);
      await Promise.all([load(), loadKeyword(kwId)]);
      setTab(r.insights.length ? "insights" : "changes");
    } catch (e: any) { setErr(String(e.message ?? e)); setStatus(null); }
    finally { setBusy(false); }
  };

  const addComp = async () => {
    const domain = newComp.domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
    if (domain.length < 4) return;
    try { await api.addCompetitor(id, { name: newComp.name.trim() || domain.split(".")[0], domain }); setNewComp({ name: "", domain: "" }); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
  };
  // Destructive and not recoverable — snapshots hold raw SerpApi payloads that cost
  // real quota — so each of these confirms first and names what goes with it.
  const removeComp = async (cid: number, name: string) => {
    if (!confirm(`Delete ${name}? Its creatives and brand term go too. This cannot be undone.`)) return;
    try { await api.deleteCompetitor(id, cid); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
  };
  const removeKw = async (kid: number, term: string) => {
    if (!confirm(`Delete the keyword "${term}"? Its collected ads, products and demand history go too.`)) return;
    try { await api.deleteKeyword(id, kid); setKwId(null); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
  };
  const removeWatchlist = async () => {
    if (!confirm(`Delete the whole watchlist "${w?.name}"? Every run, creative, ad and insight under it is deleted. This cannot be undone.`)) return;
    try { await api.deleteWatchlist(id); router.push("/watchlists"); } catch (e: any) { setErr(String(e.message ?? e)); }
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
            {w.vertical} · {w.geo}{w.location ? ` · ${w.location}` : ""} · {w.competitors.length} competitors · {w.keywords.filter((k) => (k.kind ?? "keyword") === "keyword").length} keywords · last run {fmtTime(w.last_run?.finished_at)}{w.last_run ? ` (${w.last_run.searches_used} searches)` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu watchlistId={id} />
          <button className="btn btn-primary" onClick={collect} disabled={busy}>{busy ? "Collecting…" : "Collect now"}</button>
          <button className="btn text-sm" onClick={removeWatchlist} disabled={busy}>Delete watchlist</button>
        </div>
      </div>
      {status && <div className="panel-2 p-2 mt-3 text-sm">{status}</div>}
      {err && <div className="panel p-2 mt-3 text-sm" style={{ color: "var(--high)" }}>{err}</div>}

      <nav className="flex gap-1 mt-5 border-b" style={{ borderColor: "var(--line)" }}>
        {(["insights", "changes", "brands", "competitors", "keywords"] as Tab[]).map((t) => (
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

      {tab === "brands" && (
        <div className="mt-4">
          {brands ? <BrandDefenceTable b={brands} /> : <div className="muted text-sm">loading…</div>}
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
          <div className="panel-2 p-3 flex flex-wrap gap-2 items-center">
            <span className="muted text-xs">Last {DEFAULT_WINDOW_MONTHS} months · sort by</span>
            <select
              className="panel-2 p-1.5 text-sm"
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as CreativeSortKey)}
              aria-label="Sort creatives by"
            >
              <option value="last_shown">Last shown</option>
              <option value="first_shown">First shown</option>
              <option value="total_days_shown">Days running</option>
              <option value="format">Format</option>
            </select>
            <button
              className="btn text-sm"
              onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
              aria-label={`Sort ${sortDir === "asc" ? "ascending" : "descending"}`}
              title={sortDir === "asc" ? "Ascending — click for descending" : "Descending — click for ascending"}
            >
              {sortDir === "asc" ? "ASC ↑" : "DESC ↓"}
            </button>
          </div>
          {w.competitors.map((c) => {
            const mine = sortCreatives(withinMonths(creatives.filter((x) => x.competitor_id === c.id)), sortKey, sortDir);
            return (
              <section key={c.id}>
                <div className="flex items-baseline gap-3">
                  <h2 className="font-medium text-lg">{c.name}</h2>
                  <span className="muted text-sm">{c.domain} · {c.active_creatives} active creatives · showing {mine.length}</span>
                  <button className="btn text-xs ml-auto" onClick={() => removeComp(c.id, c.name)}>Delete</button>
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
            {w.keywords.filter((k) => (k.kind ?? "keyword") === "keyword").map((k) => (
              <span key={k.id} className="inline-flex items-center">
                <button className="btn" style={kwId === k.id ? { borderColor: "var(--accent)" } : {}} onClick={() => setKwId(k.id)}>
                  {k.term}
                </button>
                <button className="btn text-xs ml-1" aria-label={`Delete keyword ${k.term}`} onClick={() => removeKw(k.id, k.term)}>×</button>
              </span>
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
