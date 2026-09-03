"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { signOut, xano, xanoEnabled } from "@/lib/xano";
import { ThemeToggle } from "./ThemeToggle";
import type { XanoMe } from "@/lib/types";

const LINKS: { href: string; label: string; match: (p: string) => boolean }[] = [
  { href: "/", label: "Dashboard", match: (p) => p === "/" },
  { href: "/watchlists", label: "Watchlists", match: (p) => p.startsWith("/watchlists") },
  { href: "/alerts", label: "Alerts", match: (p) => p.startsWith("/alerts") },
  { href: "/usage", label: "Usage & plan", match: (p) => p.startsWith("/usage") },
  { href: "/settings/integrations", label: "Integrations", match: (p) => p.startsWith("/settings") },
];

export function Nav() {
  const path = usePathname();
  const [unread, setUnread] = useState<number>(0);
  const [me, setMe] = useState<XanoMe | null>(null);
  // Every route someone reaches while signed out. Showing the app nav — and the
  // workspace name beside it — to an unauthenticated visitor is both odd and leaky.
  const onLogin = ["/login", "/forgot-password", "/reset-password"].some((p) => path.startsWith(p));

  useEffect(() => {
    if (!xanoEnabled || onLogin) return;
    let stop = false;
    const tick = () => {
      xano.alerts().then((r) => { if (!stop) setUnread(r.unread); }).catch(() => {});
    };
    xano.me().then((m) => { if (!stop) setMe(m); }).catch(() => {});
    tick();
    const t = setInterval(tick, 45_000);
    const bump = () => tick();
    window.addEventListener("adwatch:alerts-changed", bump);
    return () => { stop = true; clearInterval(t); window.removeEventListener("adwatch:alerts-changed", bump); };
  }, [onLogin, path]);

  return (
    <header className="border-b" style={{ borderColor: "var(--line)" }}>
      <div className="mx-auto max-w-6xl px-5 py-3 flex items-center gap-5">
        {/* Accessible name is the brand alone. Naming the destination here ("…—
            dashboard") collides with the Dashboard nav tab: getByRole matches names
            by substring, so the logo answered to it too and the nav-tab and
            signed-out assertions both broke. */}
        <Link href="/" aria-label="AdWatch" className="flex items-center shrink-0">
          {/* Outlined lockups, swapped by CSS in globals.css. alt must name the
              brand: the image is now the header's only accessible name. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="logo-dark" src="/logo.svg" alt="AdWatch" style={{ height: 26, width: "auto" }} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="logo-light" src="/logo-light.svg" alt="AdWatch" style={{ height: 26, width: "auto" }} />
        </Link>
        {!onLogin && (
          <nav className="flex items-center gap-1 text-sm">
            {LINKS.map((l) => (
              <Link key={l.href} href={l.href} className="tab" data-active={l.match(path)} style={{ color: l.match(path) ? "var(--text)" : "var(--muted)" }}>
                {l.label}
                {l.href === "/alerts" && unread > 0 && (
                  <span className="badge sev-high ml-2" title={`${unread} unread alerts`}>{unread}</span>
                )}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          <ThemeToggle />
          {me ? (
            <>
              <span className="muted">{me.workspace.name}</span>
              <span className="badge kind">{me.workspace.plan}</span>
              <button className="btn" onClick={signOut}>Sign out</button>
            </>
          ) : xanoEnabled && !onLogin ? (
            <Link href="/login" className="btn">Sign in</Link>
          ) : null}
        </div>
      </div>
    </header>
  );
}
