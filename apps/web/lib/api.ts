import { authHeaders } from "./auth";
import type {
  Change,
  CollectAnalyzeOut,
  Creative,
  Insight,
  SerpOut,
  TrendsOut,
  UsageOut,
  WatchlistDetail,
  WatchlistSummary,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...authHeaders(), ...(init.headers ?? {}) },
    cache: "no-store",
  });
  if (r.status === 401 && typeof window !== "undefined" && process.env.NEXT_PUBLIC_AUTH_PROVIDER === "xano" && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {}
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

export const api = {
  health: () => req<{ status: string; db: string; serpapi_key: boolean; anthropic_key: boolean }>("/health"),
  watchlists: () => req<WatchlistSummary[]>("/watchlists"),
  watchlist: (id: number) => req<WatchlistDetail>(`/watchlists/${id}`),
  createWatchlist: (body: { name: string; vertical: string; geo?: string; location?: string | null }) =>
    req<WatchlistDetail>("/watchlists", { method: "POST", body: JSON.stringify(body) }),
  addCompetitor: (id: number, body: { name: string; domain: string }) =>
    req(`/watchlists/${id}/competitors`, { method: "POST", body: JSON.stringify(body) }),
  addKeyword: (id: number, term: string) =>
    req(`/watchlists/${id}/keywords`, { method: "POST", body: JSON.stringify({ term }) }),
  changes: (id: number, limit = 50) => req<Change[]>(`/watchlists/${id}/changes?limit=${limit}`),
  insights: (id: number) => req<Insight[]>(`/watchlists/${id}/insights`),
  creatives: (id: number, competitorId?: number) =>
    req<Creative[]>(`/watchlists/${id}/creatives?active=true${competitorId ? `&competitor_id=${competitorId}` : ""}`),
  serp: (id: number, keywordId: number) => req<SerpOut>(`/watchlists/${id}/serp?keyword_id=${keywordId}`),
  trends: (id: number, keywordId: number) => req<TrendsOut>(`/watchlists/${id}/trends?keyword_id=${keywordId}`),
  collectAndAnalyze: (id: number) => req<CollectAnalyzeOut>(`/watchlists/${id}/collect-and-analyze`, { method: "POST" }),
  seedSynthetic: () => req<{ watchlist_id: number }>("/demo/seed", { method: "POST", body: JSON.stringify({ mode: "synthetic" }) }),
  usage: () => req<UsageOut>("/usage"),
  /** Downloads a generated report; returns the filename. Uses fetch so auth headers apply. */
  downloadReport: async (id: number, audience: "cfo" | "marketing", format: "pdf" | "docx" | "md", days = 7) => {
    const r = await fetch(`${BASE}/watchlists/${id}/report?audience=${audience}&format=${format}&days=${days}`, { headers: authHeaders(), cache: "no-store" });
    if (!r.ok) throw new Error(`${r.status}: report failed`);
    const blob = await r.blob();
    const cd = r.headers.get("content-disposition") ?? "";
    const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? `adwatch-report.${format}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    return name;
  },
};
