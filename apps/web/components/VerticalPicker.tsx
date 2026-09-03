"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TrendsCategory } from "@/lib/types";

/**
 * Typeahead over Google's Trends taxonomy. Pre-filled with Claude's pick and one click
 * to change — the correction is the point. Chasing a perfect classifier is the wrong
 * goal; making the fix cheap and capturing it is the right one, because that log is an
 * eval set nobody had to invent.
 */
export function VerticalPicker({
  value,
  onChange,
}: Readonly<{ value: TrendsCategory | null; onChange: (v: TrendsCategory | null, corrected: boolean) => void }>) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<TrendsCategory[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([]);
      return;
    }
    let stale = false;
    const t = setTimeout(() => {
      api
        .searchVerticals(query)
        .then((r) => !stale && setHits(r))
        .catch(() => !stale && setHits([]));
    }, 180);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [query]);

  return (
    <div data-testid="vertical-picker">
      <div className="flex items-center gap-2 flex-wrap">
        {value ? (
          <span className="badge kind" style={{ fontSize: 12 }}>
            {value.name}
          </span>
        ) : (
          <span className="muted text-sm">no vertical chosen</span>
        )}
        <button type="button" className="muted text-xs underline" onClick={() => setOpen((o) => !o)}>
          {open ? "cancel" : "change"}
        </button>
      </div>

      {open && (
        <div className="mt-2">
          <input
            className="panel-2 p-2 text-sm w-full"
            placeholder="Search Google's categories…"
            aria-label="Search verticals"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {hits.length > 0 && (
            <ul className="panel mt-1" style={{ listStyle: "none", margin: 0, padding: 4 }}>
              {hits.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    className="text-sm w-full text-left p-2"
                    style={{ background: "transparent", color: "var(--text)" }}
                    onClick={() => {
                      // corrected=true: the user overrode Claude, which is the signal worth logging
                      onChange(h, true);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    {h.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
