"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const AUDIENCES = [
  { key: "cfo", label: "CFO / Finance", hint: "spend & risk framing" },
  { key: "marketing", label: "Marketing managers", hint: "creative & keyword actions" },
] as const;
const FORMATS = ["pdf", "docx", "md"] as const;

export function ExportMenu({ watchlistId }: { watchlistId: number }) {
  const [open, setOpen] = useState(false);
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const go = async (audience: "cfo" | "marketing", format: "pdf" | "docx" | "md") => {
    const key = `${audience}:${format}`;
    setBusy(key); setMsg(null);
    try {
      const name = await api.downloadReport(watchlistId, audience, format, days);
      setMsg(`Downloaded ${name}`);
      setOpen(false);
    } catch (e: any) { setMsg(String(e.message ?? e)); }
    finally { setBusy(null); }
  };

  return (
    <div ref={ref} className="relative inline-block">
      <button className="btn" onClick={() => setOpen((o) => !o)} disabled={!!busy}>{busy ? "Generating…" : "Export report ▾"}</button>
      {open && (
        <div className="panel absolute right-0 mt-2 p-3 z-20" style={{ width: 340 }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Generate a brief</span>
            <label className="muted text-xs flex items-center gap-1">
              last
              <select className="panel-2 px-1 py-0.5 text-xs" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                {[1, 7, 14, 30].map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              days
            </label>
          </div>
          {AUDIENCES.map((a) => (
            <div key={a.key} className="panel-2 p-2 mb-2">
              <div className="text-sm">{a.label}</div>
              <div className="muted text-xs mb-1.5">{a.hint} — AI executive summary tailored to this reader</div>
              <div className="flex gap-1.5">
                {FORMATS.map((f) => (
                  <button key={f} className="btn text-xs uppercase" onClick={() => go(a.key, f)} disabled={!!busy}>{f}</button>
                ))}
              </div>
            </div>
          ))}
          {msg && <div className="muted text-xs mt-1">{msg}</div>}
        </div>
      )}
    </div>
  );
}
