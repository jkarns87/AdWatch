import type { TrendsOut } from "@/lib/types";

export function TrendSparkline({ t }: { t: TrendsOut }) {
  const pts = t.timeline;
  const w = 520, h = 90, pad = 6;
  const max = Math.max(1, ...pts.map((p) => p.value));
  const path = pts
    .map((p, i) => {
      const x = pad + (i * (w - 2 * pad)) / Math.max(1, pts.length - 1);
      const y = h - pad - (p.value / max) * (h - 2 * pad);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const last = pts[pts.length - 1];
  return (
    <div className="panel p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-medium">Demand · “{t.keyword.term}”</h3>
        <span className="muted text-xs">latest {last?.value ?? "—"} / 100</span>
      </div>
      {pts.length > 1 ? (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full mt-2" role="img" aria-label="interest over time">
          <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" />
          {last && (
            <circle cx={w - pad} cy={h - pad - (last.value / max) * (h - 2 * pad)} r="3.5" fill="var(--accent)" />
          )}
        </svg>
      ) : (
        <div className="muted text-sm mt-2">no trend data yet</div>
      )}
      {t.related_rising.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="muted">rising: </span>
          {t.related_rising.slice(0, 5).map((r) => (
            <span key={r.query} className="badge kind mr-1 mb-1">{r.query} · {r.value_text}</span>
          ))}
        </div>
      )}
    </div>
  );
}
