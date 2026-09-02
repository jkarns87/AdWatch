import type { Creative } from "@/lib/types";

export function CreativeCard({ c, isNew }: { c: Creative; isNew: boolean }) {
  return (
    <a href={c.details_url ?? "#"} target="_blank" rel="noreferrer" className="panel-2 p-3 block hover:border-[var(--accent)]" style={{ color: "var(--text)" }}>
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
      <div className="muted text-[11px] mt-2">
        {c.first_shown ?? "?"} → {c.last_shown ?? "?"}
      </div>
    </a>
  );
}
