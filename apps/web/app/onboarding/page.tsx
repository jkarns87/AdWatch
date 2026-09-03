"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { hasToken } from "@/lib/auth";
import { VerticalPicker } from "@/components/VerticalPicker";
import type { OnboardingProposal, TrendsCategory } from "@/lib/types";

/**
 * Two screens. The old wizard asked for a vertical from a list of eight, then competitor
 * domains typed from memory — what the user is least able to supply. Now: three fields,
 * Claude reads the site, and the only thing needing confirmation is the competitor list.
 *
 * A wrong keyword is cheap and self-evident: an empty paid block on the first run, then
 * you delete it. A wrong competitor burns a SerpApi search every run forever and quietly
 * skews share of voice while looking legitimate. The human goes where the cost is.
 */
export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState<"ask" | "review">("ask");

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");

  const [proposal, setProposal] = useState<OnboardingProposal | null>(null);
  const [vertical, setVertical] = useState<TrendsCategory | null>(null);
  const [keywords, setKeywords] = useState("");
  const [chosen, setChosen] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!hasToken()) router.replace("/login");
  }, [router]);

  const analyse = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("Reading the site…");
    setErr(null);
    try {
      const p = await api.analyzeCompany({ name: name.trim(), domain: domain.trim(), description: description.trim() });
      setProposal(p);
      setVertical(p.vertical);
      setKeywords(p.keywords.join("\n"));
      // Everything Claude proposed starts checked; unchecking is the cheap action.
      setChosen(Object.fromEntries(p.competitors.map((c) => [c.domain, true])));
      setStep("review");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const create = async () => {
    const kept = Object.entries(chosen).filter(([, on]) => on).map(([d]) => d);
    const plural = kept.length === 1 ? "" : "s";
    setBusy(kept.length ? `Checking ${kept.length} competitor${plural}…` : "Creating…");
    setErr(null);
    try {
      const r = await api.createFromOnboarding({
        name: name.trim(),
        domain: domain.trim(),
        description: description.trim(),
        vertical_id: vertical?.id ?? null,
        keywords: keywords.split(/[\n,]/).map((k) => k.trim()).filter(Boolean),
        competitors: kept,
        assets: proposal?.assets ?? [],
      });
      if (r.skipped.length) {
        // Say what was dropped rather than quietly persisting less than they confirmed.
        setErr(
          `Created, but ${r.skipped.length} not added: ` +
            r.skipped.map((s) => `${s.domain} (${s.reason})`).join(", "),
        );
        setTimeout(() => router.push(`/watchlists/${r.watchlist_id}`), 2500);
      } else {
        router.push(`/watchlists/${r.watchlist_id}`);
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const keptCount = Object.values(chosen).filter(Boolean).length;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold tracking-tight">
        {step === "ask" ? "Tell us about your company" : "Check what we found"}
      </h1>

      {err && (
        <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>
          {err}
        </div>
      )}

      {step === "ask" && (
        <form onSubmit={analyse} className="panel p-5 mt-4 grid gap-3" data-testid="onboarding-form">
          <p className="muted text-sm">
            We read your site and work out the vertical, the keywords worth watching, and who
            you&apos;re competing with in the paid results.
          </p>
          <input className="panel-2 p-2 text-sm" required aria-label="Company name" placeholder="Company name"
                 value={name} onChange={(e) => setName(e.target.value)} />
          <input className="panel-2 p-2 text-sm" required aria-label="Website" placeholder="yourcompany.com"
                 value={domain} onChange={(e) => setDomain(e.target.value)} />
          <textarea className="panel-2 p-2 text-sm h-24" aria-label="What you sell"
                    placeholder="What do you sell, and to whom?"
                    value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="btn btn-primary" type="submit" disabled={!!busy || !name.trim() || !domain.trim()}>
            {busy ?? "Analyse my site"}
          </button>
          <p className="muted text-xs">Reading your site costs no SerpApi quota.</p>
        </form>
      )}

      {step === "review" && proposal && (
        <div className="grid gap-3 mt-4" data-testid="onboarding-review">
          {!proposal.site_read && (
            <div className="panel p-3 text-sm" style={{ color: "var(--medium)" }}>
              We couldn&apos;t read {domain}, so this is based on your description alone. Worth a closer look.
            </div>
          )}

          <section className="panel p-4">
            <div className="font-medium">Vertical</div>
            <p className="muted text-xs mt-1 mb-2">Scopes demand data to your category.</p>
            <VerticalPicker value={vertical} onChange={(v) => setVertical(v)} />
          </section>

          <section className="panel p-4">
            <div className="font-medium">Keywords</div>
            <p className="muted text-xs mt-1 mb-2">
              One per line. A keyword that turns out to be wrong just shows an empty paid block — delete it then.
            </p>
            <textarea className="panel-2 p-2 text-sm h-28 w-full font-mono" aria-label="Keywords"
                      value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </section>

          <section className="panel p-4" data-testid="competitor-review">
            <div className="font-medium">Competitors</div>
            <p className="muted text-xs mt-1 mb-2">
              The one thing worth your eye. Each kept domain is checked against Google&apos;s Ads
              Transparency Center before it&apos;s added, and costs one search.
            </p>

            <label className="flex items-center gap-2 text-sm py-2" style={{ borderBottom: "1px solid var(--line)" }}>
              <input type="checkbox" checked disabled aria-label="Your own domain" />
              <span className="font-mono">{domain.trim()}</span>
              <span className="badge kind ml-auto">you</span>
            </label>

            {proposal.competitors.length === 0 && (
              <p className="muted text-sm mt-3">
                None found. You can add competitors on the watchlist once it exists.
              </p>
            )}
            {proposal.competitors.map((c) => (
              <label key={c.domain} className="flex items-start gap-2 text-sm py-2"
                     style={{ borderBottom: "1px solid var(--line)" }}>
                <input type="checkbox" className="mt-1" aria-label={c.domain}
                       checked={!!chosen[c.domain]}
                       onChange={(e) => setChosen((s) => ({ ...s, [c.domain]: e.target.checked }))} />
                <span>
                  <span className="font-mono">{c.domain}</span>
                  {c.reason && <span className="muted text-xs block">{c.reason}</span>}
                </span>
              </label>
            ))}
          </section>

          <div className="flex justify-between items-center gap-2 flex-wrap">
            <button className="btn" onClick={() => setStep("ask")} disabled={!!busy}>Back</button>
            <span className="muted text-xs">
              {keptCount} competitor{keptCount === 1 ? "" : "s"} · {keptCount} search{keptCount === 1 ? "" : "es"} to verify
            </span>
            <button className="btn btn-primary" onClick={create} disabled={!!busy}>
              {busy ?? "Create watchlist"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
