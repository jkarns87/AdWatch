"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

/** Shared with the blocking script in app/layout.tsx — keep both in sync. */
const KEY = "adwatch-theme";

const OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  // The server can't know the stored value, so we start at "system" and correct
  // on mount. No flash results: layout.tsx already set data-theme before paint —
  // only this control's own highlight settles.
  useEffect(() => {
    try {
      const stored = localStorage.getItem(KEY);
      setTheme(stored === "light" || stored === "dark" ? stored : "system");
    } catch {}
  }, []);

  const apply = (next: Theme) => {
    setTheme(next);
    try {
      if (next === "system") {
        localStorage.removeItem(KEY);
        document.documentElement.removeAttribute("data-theme");
      } else {
        localStorage.setItem(KEY, next);
        document.documentElement.setAttribute("data-theme", next);
      }
    } catch {}
  };

  return (
    <div
      className="flex items-center gap-0.5 rounded-lg p-0.5"
      style={{ border: "1px solid var(--line)" }}
      role="group"
      aria-label="Colour theme"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => apply(o.value)}
          aria-pressed={theme === o.value}
          className="rounded-md px-2 py-1 text-xs"
          style={{
            background: theme === o.value ? "var(--accent)" : "transparent",
            color: theme === o.value ? "var(--on-accent)" : "var(--muted)",
            fontWeight: theme === o.value ? 600 : 400,
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
