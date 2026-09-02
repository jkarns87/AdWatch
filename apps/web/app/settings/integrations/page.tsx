"use client";

import { useCallback, useEffect, useState } from "react";
import { xano, xanoEnabled } from "@/lib/xano";
import type { AlertPref, AlertProvider, Severity } from "@/lib/types";

interface ProviderMeta {
  key: AlertProvider;
  name: string;
  channel: "in_app" | "webhook" | "email";
  glyph: string;
  placeholder: string;
  help: string;
}

const PROVIDERS: ProviderMeta[] = [
  { key: "slack", name: "Slack", channel: "webhook", glyph: "#", placeholder: "https://hooks.slack.com/services/T…/B…/…", help: "Slack → Apps → Incoming Webhooks → Add to channel → copy the URL." },
  { key: "teams", name: "Microsoft Teams", channel: "webhook", glyph: "T", placeholder: "https://….logic.azure.com/workflows/…", help: "Teams channel → Workflows → “Post to a channel when a webhook request is received” → copy the URL. Delivered as an Adaptive Card." },
  { key: "discord", name: "Discord", channel: "webhook", glyph: "D", placeholder: "https://discord.com/api/webhooks/…", help: "Server settings → Integrations → Webhooks → New webhook → copy the URL." },
  { key: "generic", name: "Webhook (JSON)", channel: "webhook", glyph: "{}", placeholder: "https://example.com/hooks/adwatch", help: "POST with {text, content} — works with Zapier, Make, n8n, PagerDuty Events, or your own service." },
  { key: "email", name: "Email", channel: "email", glyph: "@", placeholder: "growth-team@yourcompany.com", help: "One address per destination." },
];

const SEVERITIES: Severity[] = ["low", "medium", "high"];

function providerOf(p: AlertPref): ProviderMeta | { key: string; name: string; glyph: string } {
  if (p.channel === "in_app" || p.provider === "in_app") return { key: "in_app", name: "In-app inbox", glyph: "●" };
  return PROVIDERS.find((x) => x.key === p.provider) ?? { key: p.channel, name: p.channel === "email" ? "Email" : "Webhook (JSON)", glyph: p.channel === "email" ? "@" : "{}" };
}

function mask(target: string | null): string {
  if (!target) return "";
  if (target.includes("@")) return target;
  try {
    const u = new URL(target);
    return `${u.host}${u.pathname.slice(0, 18)}…`;
  } catch {
    return target.slice(0, 30) + "…";
  }
}

export default function IntegrationsPage() {
  const [prefs, setPrefs] = useState<AlertPref[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState<AlertProvider>("slack");
  const [label, setLabel] = useState("");
  const [target, setTarget] = useState("");
  const [minSev, setMinSev] = useState<Severity>("medium");

  const meta = PROVIDERS.find((p) => p.key === provider)!;

  const load = useCallback(async () => {
    if (!xanoEnabled) { setPrefs([]); return; }
    try { setPrefs(await xano.alertPrefs()); } catch (e: any) { setErr(String(e.message ?? e)); setPrefs([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await xano.addAlertPref({ channel: meta.channel, provider: meta.key, label: label || meta.name, target: target.trim(), min_severity: minSev });
      setLabel(""); setTarget("");
      await load();
    } catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  const remove = async (id: number) => {
    setBusy(true); setErr(null);
    try { await xano.deleteAlertPref(id); await load(); } catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  const addInbox = async () => {
    setBusy(true); setErr(null);
    try { await xano.addAlertPref({ channel: "in_app", provider: "in_app", label: "In-app inbox", target: "", min_severity: "low" }); await load(); }
    catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  const hasInbox = prefs?.some((p) => p.channel === "in_app") ?? false;

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
      <p className="muted text-sm mt-1 max-w-2xl">
        Where alerts go. Every insight the analyst produces is fanned out by the control plane to each destination at or above its minimum severity, and every delivery is logged. The in-app inbox is always available; add chat and email destinations for the people who don&apos;t live in AdWatch.
      </p>

      {!xanoEnabled && (
        <div className="panel p-4 mt-4 text-sm muted">
          Destinations are stored per workspace in the control plane. This deployment is running with <code>NEXT_PUBLIC_AUTH_PROVIDER=none</code>, so alerts go to the in-app inbox and the <code>WEBHOOK_URL</code> configured on the API.
        </div>
      )}

      {err && <div className="panel p-3 mt-4 text-sm" style={{ color: "var(--high)" }}>{err}</div>}

      <section className="mt-6">
        <h2 className="font-medium text-lg">Destinations</h2>
        <div className="panel mt-2 divide-y" style={{ borderColor: "var(--line)" }}>
          {prefs === null && <div className="p-4 muted text-sm">loading…</div>}
          {prefs && prefs.length === 0 && !xanoEnabled && (
            <div className="p-4 flex items-center gap-4">
              <span className="panel-2 w-9 h-9 flex items-center justify-center font-semibold" style={{ color: "var(--accent)" }}>●</span>
              <div className="min-w-0 flex-1">
                <div className="font-medium">In-app inbox<span className="muted text-xs ml-2">default</span></div>
                <div className="muted text-xs">Everything, always on. Shown under Alerts.</div>
              </div>
              <span className="badge sev-low">low+</span>
              <span className="badge kind">enabled</span>
            </div>
          )}
          {prefs && prefs.length === 0 && xanoEnabled && <div className="p-4 muted text-sm">No destinations yet.</div>}
          {prefs?.map((p) => {
            const m = providerOf(p);
            return (
              <div key={p.id} className="p-4 flex items-center gap-4">
                <span className="panel-2 w-9 h-9 flex items-center justify-center font-semibold" style={{ color: "var(--accent)" }}>{m.glyph}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{p.label || m.name}<span className="muted text-xs ml-2">{m.name}</span></div>
                  <div className="muted text-xs truncate">{p.channel === "in_app" ? "Everything, always on. Shown under Alerts." : mask(p.target)}</div>
                </div>
                <span className={`badge sev-${p.min_severity}`} title="minimum severity">{p.min_severity}+</span>
                <span className="badge kind">{p.enabled ? "enabled" : "paused"}</span>
                {xanoEnabled && <button className="btn text-xs" onClick={() => remove(p.id)} disabled={busy}>Remove</button>}
              </div>
            );
          })}
          {xanoEnabled && prefs && !hasInbox && (
            <div className="p-4 flex items-center justify-between">
              <span className="muted text-sm">The in-app inbox is off for this workspace.</span>
              <button className="btn" onClick={addInbox} disabled={busy}>Turn on in-app inbox</button>
            </div>
          )}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="font-medium text-lg">Add a destination</h2>
        <form onSubmit={add} className="panel p-5 mt-2 grid gap-4 md:grid-cols-[220px_1fr]">
          <div className="space-y-1">
            {PROVIDERS.map((p) => (
              <button
                type="button"
                key={p.key}
                className="btn w-full text-left flex items-center gap-3"
                style={provider === p.key ? { borderColor: "var(--accent)", background: "var(--panel)" } : {}}
                onClick={() => setProvider(p.key)}
              >
                <span className="font-semibold" style={{ color: "var(--accent)", width: 22 }}>{p.glyph}</span>{p.name}
              </button>
            ))}
          </div>
          <div className="space-y-3">
            <div>
              <label className="muted text-xs">Label</label>
              <input className="panel-2 w-full p-2 text-sm mt-1" placeholder={`${meta.name} — growth team`} value={label} onChange={(e) => setLabel(e.target.value)} />
            </div>
            <div>
              <label className="muted text-xs">{meta.channel === "email" ? "Email address" : "Webhook URL"}</label>
              <input className="panel-2 w-full p-2 text-sm mt-1" placeholder={meta.placeholder} value={target} onChange={(e) => setTarget(e.target.value)} required type={meta.channel === "email" ? "email" : "url"} />
              <div className="muted text-xs mt-1">{meta.help}</div>
            </div>
            <div>
              <label className="muted text-xs">Minimum severity</label>
              <div className="flex gap-2 mt-1">
                {SEVERITIES.map((s) => (
                  <button type="button" key={s} className="btn text-sm" style={minSev === s ? { borderColor: "var(--accent)" } : {}} onClick={() => setMinSev(s)}>
                    <span className={`badge sev-${s}`}>{s}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3 pt-1">
              <button className="btn btn-primary" disabled={busy || !xanoEnabled}>{busy ? "…" : `Add ${meta.name}`}</button>
              {!xanoEnabled && <span className="muted text-xs">requires the Xano control plane</span>}
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
