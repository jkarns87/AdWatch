import { authHeaders } from "./auth";
import type {
  AlertFeedItem,
  Change,
  CompanyAssetIn,
  OnboardingProposal,
  OnboardingResult,
  ProviderKind,
  SerpApiStatus,
  TrendsCategory,
  WorkspaceKey,
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
  health: () => req<{ status: string; db: string; serpapi_key_present: boolean; anthropic_key_present: boolean }>("/health"),
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
  /** One call for the whole inbox. Replaces watchlists() + insights() per watchlist. */
  alertFeed: (limit = 50) => req<AlertFeedItem[]>(`/alerts?limit=${limit}`),
  serpapiStatus: () => req<SerpApiStatus>("/providers/serpapi"),
  workspaceKeys: () => req<WorkspaceKey[]>("/workspace/keys"),
  /** Validated with the provider before it is stored; a bad key 400s. */
  putWorkspaceKey: (kind: ProviderKind, key: string) =>
    req<{ kind: string; last4: string; verified: boolean }>(`/workspace/keys/${kind}`, {
      method: "PUT",
      body: JSON.stringify({ key }),
    }),
  deleteWorkspaceKey: (kind: ProviderKind) => req(`/workspace/keys/${kind}`, { method: "DELETE" }),
  /** Reads the company's site. Costs Anthropic tokens, no SerpApi quota. */
  analyzeCompany: (body: { name: string; domain: string; description: string }) =>
    req<OnboardingProposal>("/onboarding/analyze", { method: "POST", body: JSON.stringify(body) }),
  /** Verifies each kept competitor against Ads Transparency, then builds the watchlist. */
  createFromOnboarding: (body: {
    name: string; domain: string; description: string;
    vertical_id: number | null; keywords: string[]; competitors: string[]; assets: CompanyAssetIn[];
    market_terms: string[];
  }) => req<OnboardingResult>("/onboarding/create", { method: "POST", body: JSON.stringify(body) }),
  searchVerticals: (q: string) =>
    req<TrendsCategory[]>(`/onboarding/verticals?q=${encodeURIComponent(q)}&limit=8`),
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
