"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProviderKind, WorkspaceKey } from "@/lib/types";

const PROVIDERS: { kind: ProviderKind; name: string; hint: string; placeholder: string }[] = [
  {
    kind: "serpapi",
    name: "SerpApi",
    hint: "Collection spends your own quota instead of the shared plan budget.",
    placeholder: "64-character key from serpapi.com/manage-api-key",
  },
  {
    kind: "anthropic",
    name: "Anthropic",
    hint: "The AI analyst and report summaries bill to your account.",
    placeholder: "sk-ant-…",
  },
];

export function ApiKeys() {
  const [keys, setKeys] = useState<WorkspaceKey[] | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setKeys(await api.workspaceKeys());
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setKeys([]);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const save = async (kind: ProviderKind) => {
    const key = (draft[kind] ?? "").trim();
    if (!key) return;
    setBusy(kind);
    setErr(null);
    setNote(null);
    try {
      const r = await api.putWorkspaceKey(kind, key);
      // The API checks the key with the provider before storing it, so this is not
      // an optimistic message.
      setNote(
        r.verified
          ? `${kind} key saved and verified with the provider.`
          : `${kind} key saved, but the provider could not be reached to verify it.`,
      );
      setDraft((d) => ({ ...d, [kind]: "" }));
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (kind: ProviderKind) => {
    setBusy(kind);
    setErr(null);
    setNote(null);
    try {
      await api.deleteWorkspaceKey(kind);
      setNote(`${kind} key removed — falling back to the platform key.`);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const stored = (kind: ProviderKind) => keys?.find((k) => k.kind === kind);

  return (
    <section className="mt-8" data-testid="api-keys">
      <h2 className="font-medium text-lg">API keys</h2>
      <p className="muted text-sm mt-1">
        Bring your own keys to lift the plan quota. Keys are encrypted at rest, checked with the
        provider before they are saved, and only the last four characters are ever shown back.
      </p>

      {err && (
        <div className="panel p-3 mt-3 text-sm" style={{ color: "var(--high)" }}>
          {err}
        </div>
      )}
      {note && (
        <div className="panel p-3 mt-3 text-sm" style={{ color: "var(--low)" }}>
          {note}
        </div>
      )}

      <div className="grid gap-3 mt-3">
        {PROVIDERS.map((p) => {
          const existing = stored(p.kind);
          return (
            <div key={p.kind} className="panel p-4" data-testid={`key-${p.kind}`}>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="font-medium">{p.name}</div>
                {/* textTransform none on purpose: .badge uppercases, and key characters
                    are case-sensitive — "aAbB" would display as "AABB" and match
                    nothing the user can check against their provider dashboard. */}
                {existing ? (
                  <span
                    className="badge sev-low"
                    style={{ textTransform: "none", fontFamily: "ui-monospace, Menlo, monospace" }}
                  >
                    ••••{existing.last4}
                  </span>
                ) : (
                  <span className="badge kind">platform key</span>
                )}
              </div>
              <div className="muted text-sm mt-1">{p.hint}</div>

              <div className="flex gap-2 mt-3 flex-wrap">
                <input
                  className="panel-2 p-2 text-sm flex-1"
                  style={{ minWidth: 260 }}
                  type="password"
                  autoComplete="off"
                  placeholder={existing ? "replace with a new key" : p.placeholder}
                  value={draft[p.kind] ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, [p.kind]: e.target.value }))}
                  aria-label={`${p.name} API key`}
                />
                <button
                  className="btn btn-primary"
                  onClick={() => save(p.kind)}
                  disabled={busy === p.kind || !(draft[p.kind] ?? "").trim()}
                >
                  {busy === p.kind ? "checking…" : existing ? "Replace" : "Save"}
                </button>
                {existing && (
                  <button className="btn" onClick={() => remove(p.kind)} disabled={busy === p.kind}>
                    Remove
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
