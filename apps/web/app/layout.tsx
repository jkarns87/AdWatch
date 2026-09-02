import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AdWatch",
  description: "Competitive ad intelligence that watches the market for you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b" style={{ borderColor: "var(--line)" }}>
          <div className="mx-auto max-w-6xl px-5 py-3 flex items-center gap-4">
            <Link href="/" className="font-semibold tracking-tight text-lg" style={{ color: "var(--text)" }}>
              <span style={{ color: "var(--accent)" }}>●</span> AdWatch
            </Link>
            <span className="muted text-sm">competitor ads · keyword SERPs · demand — diffed, explained, alerted</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
