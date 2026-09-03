import type { Creative } from "@/lib/types";

/** Days a creative actually served, which is not the span between first and last
 *  shown — a creative can run 947 days of a 1,000-day span, or 4. Only shown once
 *  there is enough of a run to mean something. */
function longevity(days: number | null | undefined) {
  if (days == null || days < 7) return null;
  if (days >= 365) return `${Math.floor(days / 365)}y+ running`;
  if (days >= 60) return `${Math.floor(days / 30)}mo running`;
  return `${days}d running`;
}

export function CreativeCard({ c, isNew }: { c: Creative; isNew: boolean }) {
  const days = longevity(c.total_days_shown);
  return (
    // Deliberately not a link. The whole card used to be an <a> to Google's Ads
    // Transparency page, so any click on a competitor's creative silently left the
    // app. The external hop is now an explicit, small, labelled target.
    <div className="panel-2 p-3">
      <div className="flex items-center justify-between">
        <span className="badge kind">{c.format}{c.platform ? ` · ${c.platform.toLowerCase()}` : ""}</span>
        {isNew && <span className="badge sev-medium">new</span>}
      </div>
      {c.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={c.image_url} alt="" className="mt-2 w-full rounded-md object-cover" style={{ maxHeight: 140 }} />
      ) : (
        <div className="mt-2 text-sm">
          <div className="font-medium">{c.text?.headline ?? c.text?.title ?? "(text ad)"}</div>
          {c.text?.description && <div className="muted text-xs mt-1 line-clamp-2">{c.text.description}</div>}
        </div>
      )}
      <div className="muted text-[11px] mt-2 flex items-center justify-between gap-2">
        <span>
          {c.first_shown ?? "?"} → {c.last_shown ?? "?"}
          {days && <> · <span style={{ color: "var(--text)" }}>{days}</span></>}
        </span>
        {c.details_url && (
          <a
            href={c.details_url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 hover:underline"
            title="Open this creative in Google's Ads Transparency Center"
          >
            Google ↗
          </a>
        )}
      </div>
    </div>
  );
}
