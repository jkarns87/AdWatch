"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { hasToken } from "@/lib/auth";

type Comp = { name: string; domain: string };

const VERTICALS = ["specialty coffee", "meal kits", "mattresses", "VPN", "fitness apps", "online banking", "B2B SaaS", "other"];

function cleanDomain(s: string) {
  return s.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
}

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [vertical, setVertical] = useState("specialty coffee");
  const [geo, setGeo] = useState("US");
  const [location, setLocation] = useState("San Francisco, California, United States");
  const [comps, setComps] = useState<Comp[]>([{ name: "", domain: "" }, { name: "", domain: "" }, { name: "", domain: "" }]);
  const [keywords, setKeywords] = useState("");
  const [runNow, setRunNow] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { if (!hasToken()) router.replace("/login"); }, [router]);

  const validComps = comps.map((c) => ({ name: c.name.trim() || cleanDomain(c.domain).split(".")[0], domain: cleanDomain(c.domain) })).filter((c) => c.domain.length > 3);
  const kwList = keywords.split(/\n|,/).map((k) => k.trim()).filter(Boolean);
  const cost = validComps.length + kwList.length * 3;

  const create = async () => {
    setBusy("Creating watchlist…"); setErr(null);
    try {
      const w = await api.createWatchlist({ name: name.trim() || `${vertical} watch`, vertical, geo, location: location.trim() || null });
      for (const c of validComps) { setBusy(`Adding ${c.domain}…`); await api.addCompetitor(w.id, c); }
      for (const k of kwList) { setBusy(`Adding “${k}”…`); await api.addKeyword(w.id, k); }
      if (runNow) {
        setBusy(`Running baseline collection (${cost} SerpApi searches)…`);
        try { await api.collectAndAnalyze(w.id); } catch (e: any) { setErr(`Watchlist created, but the first collection failed: ${e.message}. You can run it from the watchlist page.`); }
      }
      router.push(`/w/${w.id}`);
    } catch (e: any) { setErr(String(e.message ?? e)); setBusy(null); }
  };

  const Field = ({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) => (
    <label className="block mb-3">
      <div className="text-sm font-medium mb-1">{label}</div>
      {children}
      {hint && <div className="muted text-xs mt-1">{hint}</div>}
    </label>
  );
  const input = "panel-2 w-full p-2 text-sm";

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center gap-2 muted text-xs mb-4">
        {["Watchlist", "Competitors", "Keywords", "Review"].map((s, i) => (
          <span key={s} className="badge" style={{ background: step === i + 1 ? "rgba(110,168,254,.15)" : "transparent", color: step === i + 1 ? "var(--accent)" : "var(--muted)", border: "1px solid var(--line)" }}>{i + 1}. {s}</span>
        ))}
      </div>

      {step === 1 && (
        <section className="panel p-5">
          <h1 className="text-xl font-semibold tracking-tight">What are we watching?</h1>
          <p className="muted text-sm mt-1 mb-4">A watchlist is one market: a vertical, the competitors in it, and the keywords you bid on.</p>
          <Field label="Watchlist name"><input className={input} placeholder="e.g. Specialty Coffee — Bay Area" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Vertical">
              <select className={input} value={vertical} onChange={(e) => setVertical(e.target.value)}>{VERTICALS.map((v) => <option key={v}>{v}</option>)}</select>
            </Field>
            <Field label="Market (geo)" hint="Country code for Search and Trends">
              <input className={input} value={geo} onChange={(e) => setGeo(e.target.value.toUpperCase().slice(0, 2))} />
            </Field>
          </div>
          <Field label="Search location (optional)" hint="Geo-targets the paid block, e.g. “San Francisco, California, United States”. Leave blank for national results.">
            <input className={input} value={location} onChange={(e) => setLocation(e.target.value)} />
          </Field>
          <div className="flex justify-end"><button className="btn btn-primary" onClick={() => setStep(2)}>Next: competitors</button></div>
        </section>
      )}

      {step === 2 && (
        <section className="panel p-5">
          <h1 className="text-xl font-semibold tracking-tight">Who are the competitors?</h1>
          <p className="muted text-sm mt-1 mb-4">Domains only — AdWatch looks each one up in the Google Ads Transparency Center. Three to five is the sweet spot.</p>
          {comps.map((c, i) => (
            <div key={i} className="grid grid-cols-5 gap-2 mb-2">
              <input className={`${input} col-span-2`} placeholder="Name (optional)" value={c.name} onChange={(e) => setComps(comps.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
              <input className={`${input} col-span-3`} placeholder="competitor-domain.com" value={c.domain} onChange={(e) => setComps(comps.map((x, j) => (j === i ? { ...x, domain: e.target.value } : x)))} />
            </div>
          ))}
          <button className="muted text-xs" onClick={() => setComps([...comps, { name: "", domain: "" }])}>+ add another</button>
          <div className="flex justify-between mt-4"><button className="btn" onClick={() => setStep(1)}>Back</button><button className="btn btn-primary" onClick={() => setStep(3)} disabled={validComps.length === 0}>Next: keywords</button></div>
        </section>
      )}

      {step === 3 && (
        <section className="panel p-5">
          <h1 className="text-xl font-semibold tracking-tight">Which keywords matter?</h1>
          <p className="muted text-sm mt-1 mb-4">One per line. Each keyword costs 3 SerpApi searches per run (paid block, trend, related queries).</p>
          <textarea className={`${input} h-40 font-mono`} placeholder={"coffee subscription\ncold brew delivery\nspecialty coffee beans"} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          <div className="flex justify-between mt-4"><button className="btn" onClick={() => setStep(2)}>Back</button><button className="btn btn-primary" onClick={() => setStep(4)} disabled={kwList.length === 0}>Next: review</button></div>
        </section>
      )}

      {step === 4 && (
        <section className="panel p-5">
          <h1 className="text-xl font-semibold tracking-tight">Review</h1>
          <div className="panel-2 p-3 mt-3 text-sm space-y-1">
            <div><span className="muted">Watchlist:</span> {name || `${vertical} watch`} · {vertical} · {geo}{location.trim() ? ` · ${location.trim()}` : ""}</div>
            <div><span className="muted">Competitors:</span> {validComps.map((c) => c.domain).join(", ")}</div>
            <div><span className="muted">Keywords:</span> {kwList.join(", ")}</div>
            <div><span className="muted">Cost per run:</span> {cost} SerpApi searches</div>
          </div>
          <label className="flex items-center gap-2 text-sm mt-4"><input type="checkbox" checked={runNow} onChange={(e) => setRunNow(e.target.checked)} /> Run the baseline collection now (the second run starts producing changes)</label>
          {err && <div className="text-sm mt-3" style={{ color: "var(--high)" }}>{err}</div>}
          <div className="flex justify-between mt-4">
            <button className="btn" onClick={() => setStep(3)} disabled={!!busy}>Back</button>
            <button className="btn btn-primary" onClick={create} disabled={!!busy}>{busy ?? "Create watchlist"}</button>
          </div>
        </section>
      )}
    </div>
  );
}
