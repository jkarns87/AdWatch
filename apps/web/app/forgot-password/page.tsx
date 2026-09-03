"use client";

import Link from "next/link";
import { useState } from "react";
import { xano, xanoEnabled } from "@/lib/xano";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await xano.forgotPassword(email.trim());
      setSent(true);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!xanoEnabled) {
    return (
      <div className="panel p-6 muted max-w-md mx-auto">
        Auth provider is <code>none</code> — there are no passwords to reset.
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>

      {sent ? (
        // Deliberately the same message whether or not the address has an account —
        // a different one here would let anyone test which emails are registered.
        <div className="panel p-5 mt-4">
          <p className="text-sm">
            If that address has an account, a reset link is on its way. It can be used once and
            expires in an hour.
          </p>
          <p className="muted text-xs mt-3">
            Nothing arrived? Check spam, then{" "}
            <button className="underline" onClick={() => setSent(false)}>
              try another address
            </button>
            .
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="panel p-5 mt-4 grid gap-3">
          <p className="muted text-sm">
            Enter the email you signed up with and we&apos;ll send a link to choose a new password.
          </p>
          <input
            className="panel-2 p-2 text-sm"
            type="email"
            required
            autoComplete="email"
            placeholder="you@company.com"
            aria-label="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {err && (
            <div className="text-sm" style={{ color: "var(--high)" }}>
              {err}
            </div>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy || !email.trim()}>
            {busy ? "sending…" : "Send reset link"}
          </button>
          <Link href="/login" className="muted text-xs text-center">
            Back to sign in
          </Link>
        </form>
      )}
    </div>
  );
}
