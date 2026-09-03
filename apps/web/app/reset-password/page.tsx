"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { xano, xanoEnabled } from "@/lib/xano";

const MIN_LENGTH = 8;

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const selector = params.get("s") ?? "";
  const verifier = params.get("v") ?? "";
  const hasToken = selector !== "" && verifier !== "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_LENGTH;
  const mismatch = confirm.length > 0 && password !== confirm;
  const ready = password.length >= MIN_LENGTH && password === confirm && hasToken;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await xano.resetPassword(selector, verifier, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!xanoEnabled) {
    return (
      <div className="panel p-6 muted">
        Auth provider is <code>none</code> — there are no passwords to reset.
      </div>
    );
  }

  if (!hasToken) {
    return (
      <div className="panel p-5">
        <p className="text-sm" style={{ color: "var(--high)" }}>
          This link is missing its token.
        </p>
        <p className="muted text-sm mt-2">
          Reset links expire after an hour and work once. <Link href="/forgot-password">Request a new one</Link>.
        </p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="panel p-5">
        <p className="text-sm">Your password has been changed. Taking you to sign in…</p>
        <Link href="/login" className="muted text-xs">Go now</Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="panel p-5 grid gap-3">
      <p className="muted text-sm">Choose a new password. At least {MIN_LENGTH} characters.</p>
      <input
        className="panel-2 p-2 text-sm"
        type="password"
        required
        autoComplete="new-password"
        placeholder="New password"
        aria-label="New password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <input
        className="panel-2 p-2 text-sm"
        type="password"
        required
        autoComplete="new-password"
        placeholder="Confirm new password"
        aria-label="Confirm new password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
      />
      {tooShort && <div className="muted text-xs">At least {MIN_LENGTH} characters.</div>}
      {mismatch && (
        <div className="text-xs" style={{ color: "var(--high)" }}>
          Those do not match.
        </div>
      )}
      {err && (
        <div className="text-sm" style={{ color: "var(--high)" }}>
          {err}
        </div>
      )}
      <button className="btn btn-primary" type="submit" disabled={busy || !ready}>
        {busy ? "saving…" : "Set new password"}
      </button>
      <Link href="/login" className="muted text-xs text-center">
        Back to sign in
      </Link>
    </form>
  );
}

export default function ResetPassword() {
  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-semibold tracking-tight">Choose a new password</h1>
      <div className="mt-4">
        {/* useSearchParams needs a Suspense boundary or the whole route opts out of
            static rendering at build time. */}
        <Suspense fallback={<div className="panel p-5 muted text-sm">loading…</div>}>
          <ResetForm />
        </Suspense>
      </div>
    </div>
  );
}
