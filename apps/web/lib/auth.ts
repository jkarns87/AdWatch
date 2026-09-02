// Auth adapter. NEXT_PUBLIC_AUTH_PROVIDER=none -> X-Workspace-Id header (dev / Xano-cut fallback).
// NEXT_PUBLIC_AUTH_PROVIDER=xano -> bearer token from Xano login stored in localStorage.
// This is the ONLY file that changes if Xano is cut (docs/XANO.md).

const PROVIDER = process.env.NEXT_PUBLIC_AUTH_PROVIDER ?? "none";
const TOKEN_KEY = "adwatch.xano.token";

export function authHeaders(): Record<string, string> {
  if (PROVIDER === "xano") {
    const t = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }
  return { "X-Workspace-Id": "1" };
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export async function xanoLogin(email: string, password: string): Promise<string> {
  const base = process.env.NEXT_PUBLIC_XANO_BASE_URL;
  if (!base) throw new Error("NEXT_PUBLIC_XANO_BASE_URL not set");
  const r = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`login failed (${r.status})`);
  const { authToken } = await r.json();
  setToken(authToken);
  return authToken;
}

export function hasToken(): boolean {
  if (PROVIDER !== "xano") return true;
  try { return !!window.localStorage.getItem(TOKEN_KEY); } catch { return false; }
}

export function logout() {
  setToken(null);
  if (typeof window !== "undefined") window.location.href = "/";
}

export const AUTH_PROVIDER = PROVIDER;
