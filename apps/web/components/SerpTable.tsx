import type { SerpOut } from "@/lib/types";

export function SerpTable({ s }: { s: SerpOut }) {
  return (
    <div className="panel p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-medium">Paid block · “{s.keyword.term}”</h3>
        <span className="muted text-xs">run #{s.run_id ?? "—"}</span>
      </div>
      <table className="w-full text-sm mt-3">
        <thead className="muted text-xs text-left">
          <tr><th className="py-1">#</th><th>advertiser</th><th>headline</th></tr>
        </thead>
        <tbody>
          {s.ads.map((a, i) => (
            <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-1.5 pr-2 muted whitespace-nowrap">{a.block === "top" ? "" : "↓"}{a.position}</td>
              <td className="py-1.5 pr-2 whitespace-nowrap">
                {a.advertiser_domain}
                {a.is_tracked_competitor && <span className="badge kind ml-2">tracked</span>}
              </td>
              <td className="py-1.5 muted truncate max-w-[360px]">{a.title}</td>
            </tr>
          ))}
          {s.ads.length === 0 && <tr><td colSpan={3} className="muted py-3">no paid results captured yet</td></tr>}
        </tbody>
      </table>
      {s.share_of_voice.length > 0 && (
        <div className="mt-3 muted text-xs">
          share of voice (all runs): {s.share_of_voice.slice(0, 5).map((v) => `${v.advertiser_domain} ×${v.appearances} (avg #${v.avg_position})`).join(" · ")}
        </div>
      )}
    </div>
  );
}
