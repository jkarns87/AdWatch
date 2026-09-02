# Routes and Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the watchlist routes under `/watchlists`, and make the UI brand-correct and theme-aware (light / dark / system).

**Architecture:** Frontend-only. Next.js App Router directory move plus a permanent redirect for links already delivered to chat channels. Theming is a pure CSS-token restructure — the app already routes 100% of its colour through `var(--*)`, so no component needs a colour change. A blocking inline script sets `data-theme` before first paint to prevent a flash.

**Tech Stack:** Next.js 15.5.2 (App Router), React, Tailwind v4, plain CSS custom properties, `localStorage`.

**Spec:** `docs/superpowers/specs/2026-09-02-routes-and-brand-design.md`

## Global Constraints

- No API changes, no schema changes, no new endpoints.
- No component (`.tsx`) may gain a hardcoded colour. All colour goes through `var(--*)`. Current count of hardcoded hex in `.tsx`: **0**. It must stay 0.
- Every token must have a value on bare `:root`. No colour may be defined *only* inside a media query or attribute selector.
- Logo SVGs must contain zero `<text>` elements.
- There is no web test suite. `npm run typecheck` and `npm run build` are the test cycle, plus the explicit `grep` assertions in each task.
- Light-mode contrast floor: 4.5:1 for text tokens against `--bg`.
- Run all `npm` commands from `apps/web`.

---

### Task 1: Outline the three mark SVGs

**Files:**
- Modify: `apps/web/public/mark.svg`
- Modify: `docs/brand/adwatch-mark.svg`
- Modify: `docs/brand/adwatch-mark-light.svg`
- Use: `<scratchpad>/outline/outline.js`, `<scratchpad>/outline/Poppins-Bold.ttf`

**Interfaces:**
- Consumes: nothing.
- Produces: mark assets with no font dependency. Task 7 relies on `logo.svg` / `logo-light.svg` (already outlined); this task closes the remaining three.

- [ ] **Step 1: Confirm the defect exists**

```bash
cd /Users/joseph.karns/Documents/Repositories/AdWatch
grep -c '<text' apps/web/public/mark.svg docs/brand/adwatch-mark.svg docs/brand/adwatch-mark-light.svg
```

Expected: each reports `1`.

- [ ] **Step 2: Extend the outline script to handle mark files**

The mark files contain only the small `Ad` (`x="225" y="239"` `font-size="22"` `text-anchor="middle"`). The glyph path for it is already computed in `outline.js` as `smallD`. Add a second pass writing `out-mark-<name>.svg` for each of the three inputs, replacing `SMALL_TEXT_RE` only.

- [ ] **Step 3: Run and assert zero `<text>` remains**

```bash
grep -c '<text' apps/web/public/mark.svg docs/brand/adwatch-mark.svg docs/brand/adwatch-mark-light.svg
```

Expected: each reports `0`.

- [ ] **Step 4: Render and eyeball against the reference**

```bash
rsvg-convert -w 256 -b '#ffffff' apps/web/public/mark.svg -o /tmp/mark-check.png
```

Open `/tmp/mark-check.png`. The word `Ad` inside the white tile must be Poppins Bold, horizontally centred in its navy pill, not clipped.

- [ ] **Step 5: Commit**

```bash
git add apps/web/public/mark.svg docs/brand/adwatch-mark.svg docs/brand/adwatch-mark-light.svg
git commit -m "fix(brand): outline text in mark SVGs so they carry no font dependency"
```

---

### Task 2: Publish the light logo variant to the web app

**Files:**
- Create: `apps/web/public/logo-light.svg`

**Interfaces:**
- Produces: `/logo-light.svg`, consumed by Task 7's theme-aware lockup. `/logo.svg` remains the dark variant.

- [ ] **Step 1: Copy the outlined light lockup**

```bash
cp docs/brand/adwatch-logo-light.svg apps/web/public/logo-light.svg
```

- [ ] **Step 2: Assert both public lockups are outlined and differ only in fills**

```bash
grep -c '<text' apps/web/public/logo.svg apps/web/public/logo-light.svg   # both 0
grep -o '#1f4fd8' apps/web/public/logo-light.svg | head -1                # #1f4fd8
grep -o '#6ea8fe' apps/web/public/logo.svg | head -1                      # #6ea8fe
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/public/logo-light.svg
git commit -m "feat(brand): add outlined light logo variant for light theme"
```

---

### Task 3: Three-state colour tokens in globals.css

**Files:**
- Modify: `apps/web/app/globals.css:3-14` (the `:root` block) and `:24-30` (hardcoded values)

**Interfaces:**
- Produces: `--bg --panel --panel-2 --line --text --muted --accent --on-accent --high --medium --low`, each defined on bare `:root` and overridden for dark. `--on-accent` is new and consumed by `.btn-primary`.

- [ ] **Step 1: Replace the `:root` block with the three-state structure**

```css
:root {
  --bg: #f7f9fc;
  --panel: #ffffff;
  --panel-2: #eef3fa;
  --line: #d9e2f0;
  --text: #0b1020;
  --muted: #55607d;
  --accent: #1f4fd8;
  --on-accent: #ffffff;
  --high: #c62828;
  --medium: #8a5a00;
  --low: #1a7f4b;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0b1020;
    --panel: #121a2e;
    --panel-2: #182238;
    --line: #24304d;
    --text: #e6ebf5;
    --muted: #8b96b3;
    --accent: #6ea8fe;
    --on-accent: #0b1020;
    --high: #ff6b6b;
    --medium: #ffb454;
    --low: #7dd3a0;
  }
}

:root[data-theme="dark"] {
  --bg: #0b1020;
  --panel: #121a2e;
  --panel-2: #182238;
  --line: #24304d;
  --text: #e6ebf5;
  --muted: #8b96b3;
  --accent: #6ea8fe;
  --on-accent: #0b1020;
  --high: #ff6b6b;
  --medium: #ffb454;
  --low: #7dd3a0;
}
```

The dark block is intentionally duplicated: the media query serves "system", the attribute selector serves the explicit override, and neither can substitute for the other.

- [ ] **Step 2: Fix the `.btn-primary` contrast bug**

Replace line 24. Before:

```css
.btn-primary { background: var(--accent); color: #0b1020; border-color: var(--accent); font-weight: 600; }
```

After:

```css
.btn-primary { background: var(--accent); color: var(--on-accent); border-color: var(--accent); font-weight: 600; }
```

- [ ] **Step 3: Convert the four frozen tints to `color-mix()`**

Replace lines 27–30:

```css
.sev-high   { background: color-mix(in srgb, var(--high) 15%, transparent);   color: var(--high); }
.sev-medium { background: color-mix(in srgb, var(--medium) 15%, transparent); color: var(--medium); }
.sev-low    { background: color-mix(in srgb, var(--low) 15%, transparent);    color: var(--low); }
.kind       { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); text-transform: none; }
```

- [ ] **Step 4: Assert no hardcoded colour survives outside `:root` blocks**

```bash
grep -nE '#[0-9a-fA-F]{3,8}|rgba?\(' apps/web/app/globals.css | grep -vE '^\s*[0-9]+:\s*--' | grep -v 'data-theme' | grep -v 'prefers-color-scheme'
```

Expected: no output.

- [ ] **Step 5: Build**

```bash
cd apps/web && npm run build
```

Expected: success.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/globals.css
git commit -m "feat(theme): three-state colour tokens, --on-accent, color-mix tints"
```

---

### Task 4: Prevent the flash of wrong theme

**Files:**
- Modify: `apps/web/app/layout.tsx`

**Interfaces:**
- Consumes: `data-theme` semantics from Task 3.
- Produces: `localStorage` key `adwatch-theme` with values `"light"` | `"dark"` | absent (= system). Task 5's toggle writes the same key.

- [ ] **Step 1: Add `suppressHydrationWarning` and the blocking script**

React will otherwise warn that the server HTML lacks the `data-theme` the script just added.

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
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
```

It must be inside `<head>` and must not be `async` or `defer` — it has to run before first paint.

- [ ] **Step 2: Typecheck**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 3: Verify no flash manually**

Set `localStorage.setItem('adwatch-theme','light')` in devtools, hard-reload with the OS in dark mode. The page must render light immediately — no dark frame.

- [ ] **Step 4: Commit**

```bash
git add apps/web/app/layout.tsx
git commit -m "feat(theme): set data-theme before first paint to prevent flash"
```

---

### Task 5: Theme toggle component

**Files:**
- Create: `apps/web/components/ThemeToggle.tsx`
- Modify: `apps/web/components/Nav.tsx`

**Interfaces:**
- Consumes: `adwatch-theme` key and `data-theme` attribute from Task 4.
- Produces: `export function ThemeToggle(): JSX.Element`, imported by `Nav.tsx`.

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const KEY = "adwatch-theme";
const OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

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
    <div className="flex items-center gap-0.5 rounded-lg p-0.5" style={{ border: "1px solid var(--line)" }} role="group" aria-label="Colour theme">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
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
```

The `useEffect` read is deliberate: the server cannot know the stored value, so the initial render is `"system"` and corrects on mount. This causes no flash because Task 4's script already set the attribute — only the toggle's own highlight settles.

- [ ] **Step 2: Mount it in Nav**

Add `import { ThemeToggle } from "./ThemeToggle";` and place `<ThemeToggle />` as the first child of the `ml-auto` container in `Nav.tsx`, before the workspace/sign-in block.

- [ ] **Step 3: Typecheck and build**

```bash
cd apps/web && npx tsc --noEmit && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/components/ThemeToggle.tsx apps/web/components/Nav.tsx
git commit -m "feat(theme): three-state light/dark/system toggle in nav"
```

---

### Task 6: Route restructure

**Files:**
- Move: `apps/web/app/w/` → `apps/web/app/watchlists/`
- Create: `apps/web/app/watchlists/page.tsx` (from the old `app/page.tsx`)
- Modify: `apps/web/app/page.tsx` (becomes a redirect)
- Modify: `apps/web/app/usage/page.tsx:122`, `apps/web/app/alerts/page.tsx:67,85`, `apps/web/app/onboarding/page.tsx:45`, `apps/web/components/Nav.tsx:10`
- Modify: `apps/web/next.config.ts`
- Modify: `services/api/app/alerts/webhook.py:30`, `services/api/app/alerts/xano.py:33`
- Modify: `README.md:53`

**Interfaces:**
- Produces: `/watchlists` (list), `/watchlists/[id]` (detail), `/w/:id` → 308.

- [ ] **Step 1: Move the detail route and promote the list page**

```bash
cd /Users/joseph.karns/Documents/Repositories/AdWatch
git mv apps/web/app/w apps/web/app/watchlists
git mv apps/web/app/page.tsx apps/web/app/watchlists/page.tsx
```

- [ ] **Step 2: Create the interim root redirect**

`apps/web/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/watchlists");
}
```

- [ ] **Step 3: Update the five link call sites**

```bash
cd /Users/joseph.karns/Documents/Repositories/AdWatch
grep -rl '/w/\$' apps/web | xargs sed -i '' 's#/w/\$#/watchlists/\$#g'
```

Then fix `Nav.tsx:10` by hand — `sed` will not catch it because the bug is in the `match` predicate, not a template literal:

```ts
{ href: "/watchlists", label: "Watchlists", match: (p) => p.startsWith("/watchlists") },
```

`"/watchlists/1".startsWith("/w/")` is `false`, so leaving the old predicate silently stops the nav item highlighting.

- [ ] **Step 4: Add the permanent redirect**

`apps/web/next.config.ts`:

```ts
const nextConfig: NextConfig = {
  output: "standalone",
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
  async redirects() {
    return [{ source: "/w/:id", destination: "/watchlists/:id", permanent: true }];
  },
};
```

- [ ] **Step 5: Update the two backend link builders**

`services/api/app/alerts/webhook.py:30` and `services/api/app/alerts/xano.py:33` — change `/w/{watchlist.id}` to `/watchlists/{watchlist.id}` in both f-strings. These produce the URLs delivered to Slack, Discord, and Teams.

- [ ] **Step 6: Update `README.md:53`**

Change the route-table entry `` `/w/[id]` `` to `` `/watchlists/[id]` ``.

- [ ] **Step 7: Assert no stale route references**

```bash
grep -rn '"/w/\|/w/\${\|`/w/\|/w/{' apps services README.md --include='*.tsx' --include='*.ts' --include='*.py' --include='*.md' | grep -v 'source: "/w/:id"'
```

Expected: no output.

- [ ] **Step 8: Typecheck and build**

```bash
cd apps/web && npx tsc --noEmit && npm run build
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(routes): move watchlists to /watchlists, redirect /w/:id"
```

---

### Task 7: Theme-aware logo lockup

**Files:**
- Modify: `apps/web/components/Nav.tsx` (the brand link)
- Modify: `apps/web/app/globals.css` (append the swap rules)

**Interfaces:**
- Consumes: `/logo.svg` (dark) and `/logo-light.svg` (light) from Task 2; `data-theme` from Task 3.

- [ ] **Step 1: Append the swap rules to globals.css**

```css
.logo-dark { display: none; }
.logo-light { display: block; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .logo-dark { display: block; }
  :root:not([data-theme="light"]) .logo-light { display: none; }
}
:root[data-theme="dark"] .logo-dark { display: block; }
:root[data-theme="dark"] .logo-light { display: none; }
```

`<picture>` with `prefers-color-scheme` cannot be used here — it does not see `data-theme`, so an explicit override would show the wrong lockup.

- [ ] **Step 2: Replace the hand-typed wordmark in Nav.tsx**

Replace the whole brand `<Link>` body. Before, it renders `mark.svg` plus literal `Ad<span>Watch</span>`. After:

```tsx
<Link href="/watchlists" aria-label="AdWatch — home" className="flex items-center">
  {/* eslint-disable-next-line @next/next/no-img-element */}
  <img className="logo-dark" src="/logo.svg" alt="AdWatch" height={26} style={{ height: 26, width: "auto" }} />
  {/* eslint-disable-next-line @next/next/no-img-element */}
  <img className="logo-light" src="/logo-light.svg" alt="AdWatch" height={26} style={{ height: 26, width: "auto" }} />
</Link>
```

`alt` must be `"AdWatch"` on both, not `""` — the image is now the header's only accessible name.

- [ ] **Step 3: Assert the wordmark is no longer typed in HTML**

```bash
grep -n 'Ad<span' apps/web/components/Nav.tsx
```

Expected: no output.

- [ ] **Step 4: Build and check both themes**

```bash
cd apps/web && npm run build
```

Load the app; toggle Light / Dark / System. The correct lockup must appear in each, with exactly one visible at a time.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/Nav.tsx apps/web/app/globals.css
git commit -m "feat(brand): theme-aware outlined logo lockup in nav"
```

---

### Task 8: docs/BRAND.md

**Files:**
- Create: `docs/BRAND.md`

- [ ] **Step 1: Write the document**

It must record, because nothing in the repo currently does:

- Both palettes as a table, with the measured light-mode contrast ratios (`--text` 17.95:1, `--muted` 5.93:1, `--accent` 6.28:1, `--high` 5.33:1, `--medium` 5.62:1, `--low` 4.76:1 against `--bg #f7f9fc`), and the note that `--line` at 1.24:1 is a divider, not a boundary.
- That `--accent #6ea8fe` is the logo stroke colour, so changing one desyncs the other.
- The asset matrix: which file is used where (`logo.svg` dark nav, `logo-light.svg` light nav, `mark.svg` favicon/tile, `logo-light.png` PDF + DOCX).
- **The outlining constraint** — logo SVGs contain outlined paths, not `<text>`; re-exporting from a design tool with live text silently reintroduces the Helvetica-fallback bug.
- The brand position: navy ground `#0b1020` (49% saturation at 8% luminance) is the signature, not the blue; `#1f4fd8` sits 1° of hue from Similarweb's `#195afe`, accepted deliberately.
- Severity as a brand element, with both mode-dependent value sets listed as one named scale.

- [ ] **Step 2: Commit**

```bash
git add docs/BRAND.md
git commit -m "docs: brand palette, asset matrix, and the outlining constraint"
```

---

## Verification (whole plan)

```bash
cd apps/web && npx tsc --noEmit && npm run build     # 1, 2
grep -rc '<text' apps/web/public/*.svg docs/brand/*.svg   # 3 — all 0
grep -rn '/w/' apps services README.md | grep -v '/w/:id' # 4 — empty
```

5. Load `/watchlists`, `/watchlists/1`, `/` (→ redirect), `/w/1` (→ 308).
6. Toggle Light / Dark / System; confirm palette, lockup, and primary button legibility in each.
7. Hard-reload in each theme; confirm no flash.
8. Trigger an alert; confirm the emitted `dashboard_url` contains `/watchlists/`.
