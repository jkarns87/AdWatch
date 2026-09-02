import type { ChangeKind, Severity } from "@/lib/types";

export function SeverityBadge({ s }: { s: Severity }) {
  return <span className={`badge sev-${s}`}>{s}</span>;
}

const KIND_LABEL: Record<ChangeKind, string> = {
  creative_launched: "creative launched",
  creative_dropped: "creative dropped",
  creative_surge: "creative surge",
  new_serp_advertiser: "new advertiser on keyword",
  serp_advertiser_left: "advertiser left keyword",
  serp_position_shift: "position shift",
  trend_spike: "demand spike",
  trend_decline: "demand decline",
  rising_query: "rising query",
};

export function KindBadge({ k }: { k: ChangeKind }) {
  return <span className="badge kind">{KIND_LABEL[k] ?? k}</span>;
}

export function fmtTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
