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
  ad_copy_changed: "ad copy rewritten",
  ad_sitelinks_changed: "sitelinks changed",
  product_price_changed: "price changed",
  product_promo_appeared: "promotion started",
  brand_conquest: "bidding on brand",
  brand_conquest_ended: "stopped bidding on brand",
  brand_undefended: "brand undefended",
  brand_defended: "brand defended",
};

export function KindBadge({ k }: { k: ChangeKind }) {
  return <span className="badge kind">{KIND_LABEL[k] ?? k}</span>;
}

export function fmtTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
