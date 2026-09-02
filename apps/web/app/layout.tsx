import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "AdWatch — know what your competitors did before your standup",
  description: "Competitive ad intelligence for paid-search teams: every competitor creative, every keyword they bid on, every demand shift — diffed, explained, alerted.",
  icons: { icon: "/favicon.png", apple: "/apple-touch-icon.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Must run before first paint, or every load flashes the wrong theme.
            Not async/defer on purpose. Pairs with ThemeToggle's storage key. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('adwatch-theme');if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
