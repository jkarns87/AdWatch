"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { WatchlistSummary } from "@/lib/types";
import { fmtTime } from "@/components/Badges";

export default function Home() {
  const [rows, setRows] = useState<WatchlistSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.watchlists().then(setRows).catch((e) => setErr(String(e.message ?? e)));
  useEffect(() => { load(); }, []);

  const seed = async () => {
    setBusy(true);
    try { await api.seedSynthetic(); await load(); } catch (e: any) { setErr(String(e.message ?? e)); } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Watchlists</h1>
        <div className="flex gap-2">
          <button className="btn" onClick={seed} disabled={busy} title="Fictitious advertisers, two runs, zero SerpApi quota">{busy ? "seeding…" : "Seed demo data"}</button>
          <Link href="/onboarding" className="btn btn-primary">New watchlist</Link>
        </div>
      </div>
      {err && <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>API error: {err} — is the API running on {process.env.NEXT_PUBLIC_API_BASE_URL}?</div>}
      {rows === null && !err && <div className="muted mt-4">loading…</div>}
      {rows && rows.length === 0 && (
        <div className="panel p-6 mt-4 muted">No watchlists yet. <Link href="/onboarding">Create your first watchlist</Link> or seed demo data.</div>
      )}
      <div className="grid gap-3 mt-4 sm:grid-cols-2">
        {rows?.map((w) => (
          <Link key={w.id} href={`/w/${w.id}`} className="panel p-4 block hover:border-[var(--accent)]" style={{ color: "var(--text)" }}>
            <div className="flex items-center justify-between">
              <div className="font-medium text-lg">{w.name}</div>
              {w.open_changes > 0 && <span className="badge sev-high">{w.open_changes} unreviewed</span>}
            </div>
            <div className="muted text-sm mt-1">{w.vertical} · {w.geo}</div>
            <div className="muted text-xs mt-3">{w.competitor_count} competitors · {w.keyword_count} keywords · last run {fmtTime(w.last_run_at)}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
