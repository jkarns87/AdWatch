import type { Insight } from "@/lib/types";
import { fmtTime } from "./Badges";
import { ChangeRow } from "./ChangeRow";

export function InsightCard({ i }: { i: Insight }) {
  const top = i.changes.reduce((m, c) => (c.severity === "high" ? "high" : m === "high" ? m : c.severity === "medium" ? "medium" : m), "low" as string);
  return (
    <article className="panel p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`badge sev-${top}`}>{top}</span>
          <span className="muted text-xs">{fmtTime(i.created_at)} · run #{i.run_id} · {i.changes.length} change{i.changes.length === 1 ? "" : "s"}</span>
        </div>
        <span className="muted text-xs" title={i.model}>confidence {(i.confidence * 100).toFixed(0)}%</span>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed">{i.summary}</p>
      {i.why_it_matters && (
        <p className="mt-2 text-sm muted"><span style={{ color: "var(--text)" }}>Why it matters. </span>{i.why_it_matters}</p>
      )}
      {i.recommended_actions?.length > 0 && (
        <ul className="mt-3 space-y-2">
          {i.recommended_actions.map((a, idx) => (
            <li key={idx} className="panel-2 p-3 text-sm">
              <div className="flex items-center gap-2">
                <span className="badge kind">{a.urgency?.replace("_", " ")}</span>
                <span className="muted text-xs">effort: {a.effort}</span>
              </div>
              <div className="mt-1 font-medium">{a.action}</div>
              <div className="muted text-xs mt-0.5">{a.rationale}</div>
            </li>
          ))}
        </ul>
      )}
      {i.changes.length > 0 && (
        <details className="mt-3">
          <summary className="muted text-xs cursor-pointer">evidence ({i.changes.length})</summary>
          <div className="mt-1 divide-y" style={{ borderColor: "var(--line)" }}>
            {i.changes.map((c) => <ChangeRow key={c.id} c={c} compact />)}
          </div>
        </details>
      )}
    </article>
  );
}
