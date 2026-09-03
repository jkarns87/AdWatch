// Control-plane client (Xano): identity, in-app alert inbox, alert destinations, plan.
// Only active when NEXT_PUBLIC_AUTH_PROVIDER=xano; every page that uses it has a data-plane fallback.

import { authHeaders, setToken } from "./auth";
import type { AlertPref, AlertProvider, PlanKey, Severity, XanoAlertsOut, XanoMe } from "./types";

const BASE = process.env.NEXT_PUBLIC_XANO_BASE_URL ?? "";
export const xanoEnabled = process.env.NEXT_PUBLIC_AUTH_PROVIDER === "xano" && BASE !== "";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!xanoEnabled) throw new Error("Xano control plane is not enabled (NEXT_PUBLIC_AUTH_PROVIDER != xano)");
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...authHeaders(), ...(init.headers ?? {}) },
    cache: "no-store",
  });
  if (r.status === 401 || r.status === 403) {
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      setToken(null);
      window.location.href = "/login";
    }
  }
  if (!r.ok) {
    let message = r.statusText;
    try {
      message = (await r.json()).message ?? message;
    } catch {}
    throw new Error(`${r.status}: ${message}`);
  }
  return r.json();
}

/** For the unauthenticated auth endpoints. req() redirects to /login on 401/403,
 *  which is exactly wrong on the pages someone reaches *because* they cannot sign in. */
async function publicReq<T>(path: string, body: unknown): Promise<T> {
  if (!xanoEnabled) throw new Error("Xano control plane is not enabled (NEXT_PUBLIC_AUTH_PROVIDER != xano)");
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) {
    let message = r.statusText;
    try {
      message = (await r.json()).message ?? message;
    } catch {}
    throw new Error(message);
  }
  return r.json();
}

export const xano = {
  forgotPassword: (email: string) =>
    publicReq<{ ok: boolean; message: string }>("/auth/forgot_password", { email }),
  resetPassword: (token: string, password: string) =>
    publicReq<{ ok: boolean; message: string }>("/auth/reset_password", { token, password }),
  me: () => req<XanoMe>("/auth/me"),
  alerts: () => req<XanoAlertsOut>("/alerts"),
  markRead: (id: number) => req(`/alerts/${id}/read`, { method: "POST", body: "{}" }),
  markAllRead: () => req<{ marked: number }>("/alerts/read_all", { method: "POST", body: "{}" }),
  alertPrefs: () => req<AlertPref[]>("/alert_prefs"),
  addAlertPref: (body: { channel: "in_app" | "webhook" | "email"; provider: AlertProvider; label: string; target: string; min_severity: Severity }) =>
    req<AlertPref>("/alert_prefs", { method: "POST", body: JSON.stringify(body) }),
  deleteAlertPref: (id: number) => req<{ success: boolean }>(`/alert_prefs/by_id/${id}`, { method: "DELETE" }),
  setPlan: (plan: PlanKey) => req<{ id: number; name: string; plan: PlanKey }>("/workspace/plan", { method: "POST", body: JSON.stringify({ plan }) }),
};

export function signOut() {
  setToken(null);
  if (typeof window !== "undefined") window.location.href = "/login";
}

/** Xano returns timestamps as epoch ms (number) from the CLI-built tables; tolerate ISO strings too. */
export function xanoDate(v: number | string | null | undefined): string | null {
  if (v === null || v === undefined) return null;
  return typeof v === "number" ? new Date(v).toISOString() : v;
}
