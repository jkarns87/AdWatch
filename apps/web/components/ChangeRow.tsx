import type { Change } from "@/lib/types";
import { KindBadge, SeverityBadge, fmtTime } from "./Badges";

function describe(c: Change): string {
  const p = c.payload as Record<string, any>;
  switch (c.kind) {
    case "creative_launched":
      return `${c.subject_label} launched a ${p.format ?? ""} creative${p.text?.headline ? `: “${p.text.headline}”` : ""}`;
    case "creative_dropped":
      return `${c.subject_label} dropped a ${p.format ?? ""} creative${p.text?.headline ? `: “${p.text.headline}”` : ""}`;
    case "creative_surge":
      return `${c.subject_label} went from ${p.before} to ${p.after} active creatives (+${p.delta_pct}%)`;
    case "new_serp_advertiser":
      return `${p.advertiser_domain} appeared on “${c.subject_label}” (${p.block} #${p.position})`;
    case "serp_advertiser_left":
      return `${p.advertiser_domain} left the paid block on “${c.subject_label}”`;
    case "serp_position_shift":
      return `${p.advertiser_domain} moved ${p.from_block} #${p.from_position} → ${p.to_block} #${p.to_position} on “${c.subject_label}”`;
    case "trend_spike":
      return `Interest in “${c.subject_label}” is ${p.ratio}× its 4-week average (${p.latest} vs ${p.trailing_mean})`;
    case "trend_decline":
      return `Interest in “${c.subject_label}” fell to ${p.ratio}× its 4-week average`;
    case "rising_query":
      return `“${p.query}” is ${p.value_text} for “${c.subject_label}”`;
    default:
      return c.kind;
  }
}

export function ChangeRow({ c, compact = false }: { c: Change; compact?: boolean }) {
  const p = c.payload as Record<string, any>;
  return (
    <div className="flex items-start gap-3 py-2">
      <SeverityBadge s={c.severity} />
      <div className="flex-1 min-w-0">
        <div className="text-sm">{describe(c)}</div>
        {!compact && (
          <div className="muted text-xs mt-0.5 flex gap-2 items-center">
            <KindBadge k={c.kind} />
            <span>{fmtTime(c.detected_at)}</span>
            {p.details_url && (
              <a href={p.details_url} target="_blank" rel="noreferrer">view creative ↗</a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
