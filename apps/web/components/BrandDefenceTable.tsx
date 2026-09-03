import type { BrandsOut } from "@/lib/types";

/** Who is paying for each tracked company's own name.
 *
 *  This is state, not a change feed. Conquesting fires as an event only when it
 *  starts or stops — the paid block flickers, so re-announcing a standing rival every
 *  run would bury the run where one arrives — which leaves the standing position
 *  invisible in the feed. That position is the whole point for someone defending a
 *  brand, so it gets its own view.
 */
export function BrandDefenceTable({ b }: { b: BrandsOut }) {
  if (!b.brands.length) {
    return (
      <div className="muted text-sm">
        No brand terms yet. They are created from your competitors on the next run — one
        search each.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {b.brands.map((row) => (
        <section key={row.competitor_id} className="panel-2 p-3">
          <div className="flex flex-wrap items-baseline gap-2">
            <h3 className="font-medium">{row.brand}</h3>
            {row.is_self && <span className="badge kind">you</span>}
            <span className="muted text-xs">{row.owner_domain}</span>
            {!row.collected ? (
              <span className="badge kind ml-auto">not collected yet</span>
            ) : row.undefended ? (
              <span className="badge sev-high ml-auto">undefended</span>
            ) : row.conquerors.length ? (
              <span className="badge sev-medium ml-auto">{row.conquerors.length} bidding</span>
            ) : (
              <span className="badge sev-low ml-auto">clear</span>
            )}
          </div>

          <div className="muted text-xs mt-1">
            {!row.collected
              ? "This brand term has not been collected in a completed run."
              : row.owner_present
                ? `Owner is defending at position ${row.owner_position}.`
                : row.conquerors.length
                  ? "Owner is absent from its own brand term while others bid on it."
                  : "Nobody is bidding on this term, including the owner."}
          </div>

          {row.conquerors.length > 0 && (
            <table className="w-full text-sm mt-2">
              <thead className="muted text-xs">
                <tr>
                  <th className="text-left font-normal">advertiser</th>
                  <th className="text-left font-normal">pos</th>
                  <th className="text-left font-normal">ad</th>
                </tr>
              </thead>
              <tbody>
                {row.conquerors.map((c) => (
                  <tr key={`${c.advertiser_domain}-${c.position}`}>
                    <td className="pr-3 py-0.5">{c.advertiser_domain}</td>
                    <td className="pr-3 py-0.5 muted">
                      {c.position}
                      {c.block === "bottom" ? " (btm)" : ""}
                    </td>
                    <td className="py-0.5 muted">{c.title}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ))}
    </div>
  );
}
