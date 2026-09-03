import type { Creative } from "./types";

export type CreativeSortKey = "last_shown" | "first_shown" | "total_days_shown" | "format";

/** How far back the creative grid looks, in months. A large advertiser carries years
 *  of history — one live account returned creatives still dated 947 days of run — and
 *  showing all of it buries what is running now. */
export const DEFAULT_WINDOW_MONTHS = 6;

/** The cutoff, computed in UTC.
 *
 *  getMonth/setMonth work in the viewer's local time while `last_shown` is a plain
 *  UTC date, so mixing them moved the boundary by the local offset — a viewer west
 *  of UTC excluded a creative that a viewer east of it kept, from identical data.
 */
function monthsAgo(months: number, now: Date): Date {
  const d = new Date(now);
  d.setUTCMonth(d.getUTCMonth() - months);
  return d;
}

/** Creatives seen within the window, judged on when they were last shown.
 *
 *  A creative with no `last_shown` is kept rather than dropped: we cannot date it, and
 *  silently hiding data because a field is missing is how a grid ends up lying about
 *  what an advertiser is running.
 */
export function withinMonths(rows: Creative[], months = DEFAULT_WINDOW_MONTHS, now = new Date()): Creative[] {
  const cutoff = monthsAgo(months, now);
  return rows.filter((c) => {
    if (!c.last_shown) return true;
    const seen = new Date(c.last_shown);
    return Number.isNaN(seen.getTime()) ? true : seen >= cutoff;
  });
}

function value(c: Creative, key: CreativeSortKey): number | string | null {
  if (key === "format") return c.format ?? "";
  if (key === "total_days_shown") return c.total_days_shown ?? null;
  const raw = key === "first_shown" ? c.first_shown : c.last_shown;
  if (!raw) return null;
  const t = new Date(raw).getTime();
  return Number.isNaN(t) ? null : t;
}

/** Sort a competitor's creatives.
 *
 *  Missing values always sort last regardless of direction — an undated creative is
 *  not "the oldest", it is unknown, and letting it lead an ascending sort would put
 *  the least informative rows first in both directions.
 */
export function sortCreatives(rows: Creative[], key: CreativeSortKey, dir: "asc" | "desc"): Creative[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = value(a, key);
    const bv = value(b, key);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (typeof av === "string" || typeof bv === "string") {
      return sign * String(av).localeCompare(String(bv));
    }
    return sign * (av - bv);
  });
}
