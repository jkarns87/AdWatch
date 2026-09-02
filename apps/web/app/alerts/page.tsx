"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { xano, xanoDate, xanoEnabled } from "@/lib/xano";
import type { Severity, XanoAlert } from "@/lib/types";
import { fmtTime } from "@/components/Badges";

/** One row of the inbox. Comes from Xano alert_log (channel=in_app) or, when the control plane is off,
 *  from data-plane insights so the page still demos. */
interface InboxItem {
  id: number;
  severity: Severity;
  title: string;
  summary: string;
  why: string;
  when: string | null;
  href: string;
  read: boolean;
  source: "xano" | "api";
}

type Filter = "all" | "unread" | "high";

const FALLBACK_READ_KEY = "adwatch.inbox.read";

function loadFallbackRead(): Set<number> {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(FALLBACK_READ_KEY) ?? "[]"));
  } catch {
    return new Set();
  }
}

function saveFallbackRead(s: Set<number>) {
  try {
    window.localStorage.setItem(FALLBACK_READ_KEY, JSON.stringify([...s]));
  } catch {}
}

function topSeverity(sevs: Severity[]): Severity {
  return sevs.includes("high") ? "high" : sevs.includes("medium") ? "medium" : "low";
}

export default function AlertsPage() {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const notifyNav = () => window.dispatchEvent(new Event("adwatch:alerts-changed"));

  const load = useCallback(async () => {
    setErr(null);
    try {
      if (xanoEnabled) {
        const r = await xano.alerts();
        setItems(
          r.alerts.map((a: XanoAlert) => ({
            id: a.id,
            severity: a.severity ?? "medium",
            title: a.title ?? "Alert",
            summary: a.summary ?? "",
            why: a.why_it_matters ?? "",
            when: xanoDate(a.created_at),
            href: a.watchlist_id ? `/w/${a.watchlist_id}` : a.dashboard_url ?? "/",
            read: !!a.read,
            source: "xano",
          })),
        );
      } else {
        const read = loadFallbackRead();
        const lists = await api.watchlists();
        const all = await Promise.all(lists.map(async (w) => (await api.insights(w.id)).map((i) => ({ w, i }))));
        const flat = all.flat().sort((a, b) => (a.i.created_at < b.i.created_at ? 1 : -1));
        setItems(
          flat.map(({ w, i }) => ({
            id: i.id,
            severity: topSeverity(i.changes.map((c) => c.severity)),
            title: w.name,
            summary: i.summary,
            why: i.why_it_matters,
            when: i.created_at,
            href: `/w/${w.id}`,
            read: read.has(i.id),
            source: "api",
          })),
        );
      }
    } catch (e: any) {
      setErr(String(e.message ?? e));
      setItems([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const markRead = async (item: InboxItem) => {
    if (item.read) return;
    setItems((prev) => prev?.map((x) => (x.id === item.id ? { ...x, read: true } : x)) ?? prev);
    if (item.source === "xano") {
      try { await xano.markRead(item.id); notifyNav(); } catch (e: any) { setErr(String(e.message ?? e)); }
    } else {
      const s = loadFallbackRead(); s.add(item.id); saveFallbackRead(s);
    }
  };

  const markAll = async () => {
    setBusy(true);
    try {
      if (xanoEnabled) { await xano.markAllRead(); notifyNav(); }
      else { const s = loadFallbackRead(); items?.forEach((i) => s.add(i.id)); saveFallbackRead(s); }
      await load();
    } catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  const shown = useMemo(() => {
    if (!items) return [];
    if (filter === "unread") return items.filter((i) => !i.read);
    if (filter === "high") return items.filter((i) => i.severity === "high");
    return items;
  }, [items, filter]);

  const unread = items?.filter((i) => !i.read).length ?? 0;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
          <div className="muted text-sm mt-1">
            {items ? `${items.length} alert${items.length === 1 ? "" : "s"} · ${unread} unread` : "loading…"}
            {" · "}
            {xanoEnabled ? "inbox served by the control plane (Xano alert_log)" : "showing data-plane insights — sign-in via Xano to get the shared inbox"}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 panel-2 p-1">
            {(["all", "unread", "high"] as Filter[]).map((f) => (
              <button key={f} className="tab text-sm capitalize" data-active={filter === f} onClick={() => setFilter(f)} style={{ padding: "4px 10px", borderBottom: "none", borderRadius: 8, background: filter === f ? "var(--panel)" : "transparent" }}>
                {f}{f === "unread" && unread > 0 ? ` (${unread})` : ""}
              </button>
            ))}
          </div>
          <button className="btn" onClick={markAll} disabled={busy || unread === 0}>Mark all read</button>
        </div>
      </div>

      {err && <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>{err}</div>}

      {items && items.length === 0 && !err && (
        <div className="panel p-6 mt-4 muted">
          Nothing here yet. Alerts appear when a collection run finds changes worth telling you about — run <em>Collect now</em> on a watchlist twice (the first run is the baseline).
        </div>
      )}

      <div className="mt-4 space-y-2">
        {shown.map((a) => (
          <article
            key={`${a.source}-${a.id}`}
            className="panel p-4"
            style={{ borderLeft: `3px solid var(--${a.severity})`, opacity: a.read ? 0.72 : 1, cursor: a.read ? "default" : "pointer" }}
            onClick={() => markRead(a)}
            title={a.read ? undefined : "click to mark as read"}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {!a.read && <span title="unread" style={{ width: 8, height: 8, borderRadius: 999, background: "var(--accent)", display: "inline-block" }} />}
                <span className={`badge sev-${a.severity}`}>{a.severity}</span>
                <span className="font-medium truncate">{a.title}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="muted text-xs">{fmtTime(a.when)}</span>
                <Link href={a.href} className="btn text-xs">Open watchlist</Link>
              </div>
            </div>
            <p className="mt-2 text-[15px] leading-relaxed">{a.summary}</p>
            {a.why && <p className="mt-1 text-sm muted"><span style={{ color: "var(--text)" }}>Why it matters. </span>{a.why}</p>}
          </article>
        ))}
      </div>
    </div>
  );
}
