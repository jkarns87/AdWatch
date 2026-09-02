"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setToken, xanoLogin } from "@/lib/auth";

const XANO = process.env.NEXT_PUBLIC_XANO_BASE_URL ?? "";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (mode === "login") {
        await xanoLogin(email, password);
      } else {
        const r = await fetch(`${XANO}/auth/signup`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ name, email, password }),
        });
        if (!r.ok) throw new Error((await r.json()).message ?? `signup failed (${r.status})`);
        setToken((await r.json()).authToken);
      }
      router.push("/");
    } catch (e: any) { setErr(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  if (process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "xano") {
    return <div className="panel p-6 muted">Auth provider is <code>none</code> — no login needed. Set <code>NEXT_PUBLIC_AUTH_PROVIDER=xano</code> to enable.</div>;
  }

  return (
    <div className="max-w-sm mx-auto mt-10">
      <h1 className="text-2xl font-semibold tracking-tight">{mode === "login" ? "Sign in" : "Create your workspace"}</h1>
      <form onSubmit={submit} className="panel p-5 mt-4 space-y-3">
        {mode === "signup" && (
          <input className="panel-2 w-full p-2 text-sm" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
        )}
        <input className="panel-2 w-full p-2 text-sm" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="panel-2 w-full p-2 text-sm" type="password" placeholder="Password (8+ chars)" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
        {err && <div className="text-sm" style={{ color: "var(--high)" }}>{err}</div>}
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? "…" : mode === "login" ? "Sign in" : "Sign up"}</button>
        <button type="button" className="muted text-xs w-full" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? "No account? Create one" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
