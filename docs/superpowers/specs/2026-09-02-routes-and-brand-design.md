# A + E — Route restructure and brand pass

**Date:** 2026-09-02
**Status:** Draft for review
**Scope:** Frontend only. No API changes, no schema changes, no new endpoints.

---

## Why these two together

Both changes land in the same file. The route restructure edits `Nav.tsx:10`; the brand
pass edits `Nav.tsx:41`. Splitting them means touching the same component twice and
reconciling two diffs over one header.

They are also the only two sub-projects on the backlog with no backend dependency, which
makes them shippable while the metering and alerts work is still being specified.

---

## A — Route restructure

### Decisions

| | |
|---|---|
| Watchlist detail | `/w/[id]` → `/watchlists/[id]` |
| Watchlist list | moves from `/` to `/watchlists` |
| `/` | becomes the dashboard route; ships in this change as a placeholder that redirects to `/watchlists` |
| Old links | `/w/:id` keeps working permanently via a Next.js redirect |

`/` is deliberately *not* built out here. The dashboard is sub-project D and depends on
work that does not exist yet (LLM metering, alerts read API, SerpApi health). Shipping a
half-populated dashboard would put invented numbers on the screen. Until D lands, `/`
redirects to `/watchlists` so there is no dead route and no fake data.

### Changes

**Directory**

```
git mv apps/web/app/w apps/web/app/watchlists
```

Preserves file history on `page.tsx`. Result: `apps/web/app/watchlists/[id]/page.tsx`.

**New file: `apps/web/app/watchlists/page.tsx`**

The current contents of `apps/web/app/page.tsx`, moved verbatim. It is already titled
"Watchlists" — the move only makes the URL agree with the heading.

**Replaced: `apps/web/app/page.tsx`**

Becomes a redirect to `/watchlists` (`redirect()` from `next/navigation`, server component).
Replaced wholesale when D ships.

**Link call sites (6)**

| File | Line | Change |
|---|---|---|
| `apps/web/app/watchlists/page.tsx` | 38 | `/w/${w.id}` → `/watchlists/${w.id}` |
| `apps/web/app/usage/page.tsx` | 122 | `/w/${w.watchlist_id}` → `/watchlists/${w.watchlist_id}` |
| `apps/web/app/alerts/page.tsx` | 67 | `/w/${a.watchlist_id}` → `/watchlists/${a.watchlist_id}` |
| `apps/web/app/alerts/page.tsx` | 85 | `/w/${w.id}` → `/watchlists/${w.id}` |
| `apps/web/app/onboarding/page.tsx` | 45 | `router.push('/w/${w.id}')` → `/watchlists/${w.id}` |
| `apps/web/components/Nav.tsx` | 10 | see below |

**`Nav.tsx:10` — the one that fails silently**

Current:

```ts
{ href: "/", label: "Watchlists", match: (p) => p === "/" || p.startsWith("/w/") }
```

`"/watchlists/1".startsWith("/w/")` is **false** — `/wa` ≠ `/w/`. Left unchanged, the nav
item stops highlighting on the detail page with no error and no test failure. Becomes:

```ts
{ href: "/watchlists", label: "Watchlists", match: (p) => p.startsWith("/watchlists") }
```

**Backend link builders (2)**

These generate the URLs delivered into Slack, Discord, and Teams:

- `services/api/app/alerts/webhook.py:30`
- `services/api/app/alerts/xano.py:33`

Both build `f"{dashboard_url}/w/{watchlist.id}"` → `/watchlists/{watchlist.id}`.

**Docs (1)**

`README.md:53` — the route table.

### The redirect is not optional

`xano/table/alert_log.xs:27` persists `dashboard_url` per alert, and every alert already
delivered to a chat channel contains a `/w/{id}` link. Renaming does not rewrite history.
Without a redirect, every historical alert 404s — including any a judge clicks.

`apps/web/next.config.ts`:

```ts
async redirects() {
  return [{ source: "/w/:id", destination: "/watchlists/:id", permanent: true }];
}
```

Permanent (308). Costs nothing, runs at the edge, no page file.

### Out of scope for A

- Adding a "Dashboard" nav item. It arrives with D, pointing at a real page.
- Any change to `/alerts`, `/usage`, `/settings/integrations`, `/login`, `/onboarding`,
  `/welcome` beyond the link updates listed above.

---

## E — Brand pass

### The defect

`apps/web/public/logo.svg` — identical to `docs/brand/adwatch-logo-dark.svg` — contains two
live `<text>` elements set in `font-family="Poppins, Inter, Helvetica, Arial, sans-serif"`.

An SVG referenced through `<img src>` renders in an isolated document and **cannot load
external fonts**. It falls back to a locally installed face. Poppins is not installed on the
development machine and will not be installed on a viewer's machine, so the wordmark inside
`logo.svg` renders in **Helvetica** today, everywhere it is used.

The PDF and DOCX reports are unaffected because they embed `logo-light.png`, a raster with
the type already baked in (`render_pdf.py:115`, `render_docx.py:58`).

Meanwhile `Nav.tsx:41` does not use `logo.svg` at all — it re-types the wordmark as
`Ad<span>Watch</span>` in HTML, rendered in the app's body stack
(`ui-sans-serif, system-ui, -apple-system, "Segoe UI"`).

Net result: **three different renderings of one wordmark** — Helvetica in any SVG use, the
system UI face in the nav, and Poppins in the reports.

### Decision: outline the text

Convert the two `<text>` elements in the logo SVGs to paths, producing a self-contained
asset with no font dependency. The wordmark then renders identically in the nav, on login,
in the favicon pipeline, and in reports, on every machine, with no webfont loaded at runtime.

Rejected alternatives:

- **Load Poppins via `next/font`.** Works only for HTML text, not for SVG-in-`<img>`. Would
  fix the nav and leave every SVG use still rendering in Helvetica. Also adds ~15–25 kB.
- **Inline the SVG into the React component.** Lets the SVG use a loaded webfont, but then
  Poppins must be loaded anyway, and the asset stays font-dependent everywhere else.
- **Use the PNG.** Correct rendering, but raster — needs 2x/3x variants and does not scale.

### Tooling

Neither Inkscape nor FontForge is installed. Available: `rsvg-convert`, `node 24.13.1`,
`npx`. Poppins is licensed **OFL 1.1**, which permits embedding outlines in a derived work.

Procedure — run once, commit the output, no build-step dependency:

1. Fetch `Poppins-Bold.ttf` from Google Fonts.
2. Convert the two `<text>` nodes to paths via an `npx` text-to-path tool.
3. Emit `logo-outlined.svg`; verify visually against `adwatch-logo-dark.png`.
4. Replace `apps/web/public/logo.svg` and both `docs/brand/adwatch-logo-*.svg`.
5. Confirm no `<text>` remains: `grep -c '<text' apps/web/public/logo.svg` → `0`.

The TTF is not committed. Only the resulting paths are.

### Nav lockup

`Nav.tsx:41` drops the hand-typed wordmark and uses the outlined lockup:

```tsx
<Link href="/watchlists" aria-label="AdWatch — home">
  <img src="/logo.svg" alt="AdWatch" height={27} />
</Link>
```

`alt` must be `"AdWatch"`, not `""`. The current `alt=""` is correct today because the mark
is decorative and HTML text follows it; once the image *is* the wordmark, empty alt would
leave the header with no accessible name.

### Token documentation

`globals.css` already defines the full palette (`--bg`, `--panel`, `--panel-2`, `--line`,
`--text`, `--muted`, `--accent`, `--high`, `--medium`, `--low`). It is undocumented — nothing
records that `--accent: #6ea8fe` is the same blue as the logo stroke, or that the severity
triple is load-bearing for `.sev-*` badges and the change feed.

Deliverable: a short `docs/BRAND.md` recording the palette, its provenance, the logo asset
matrix (which file is used where), and the outlining constraint so the next person does not
re-introduce live text.

### Out of scope for E

- **Typography beyond the logo.** The body stack stays as-is. Changing it is a separate
  decision with its own cost.
- **The competitive UI patterns** identified in the 2026 tooling research (creative flight
  timelines, persistent quota display, brief-as-artifact). Flight timelines belong to G;
  quota display to D.

---

### Brand colour position

Measured against the category (colours pulled from each vendor's live homepage, converted
to HSL): six of nine markers sit between 210° and 240°. Adbeat 210°, AdWatch 216°,
SpyFu 219°, Similarweb 223°, AdWatch 224°, BigSpy 240°. Adbeat and SpyFu are effectively
greyscale (7% and 10% saturation). Only Sensor Tower (teal `#00cfb8` on `#232325`) and
Foreplay (warm `#ffc852`) stepped outside the blue lane.

**`#1f4fd8` — the light-variant wordmark blue — is one degree of hue from Similarweb's
`#195afe`** (ΔRGB 40). Similarweb is the largest vendor in the category.

Two decisions:

**The navy ground is the signature, not the blue.** `#0b1020` is 49% saturated at 8%
luminance — a blue-black. Sensor Tower's dark is 3% saturated, a neutral black. Nobody else
in the set is using a saturated dark. Light mode therefore carries the navy into the header,
the mark tile, and text, so the product still reads as AdWatch on a white surface. The
Similarweb adjacency on light backgrounds is accepted rather than designed around.

**Severity is promoted from a status scale to a brand element.** The product is *what
changed and how badly*; the severity triple is already load-bearing for `.sev-*` badges, the
change feed, and the PDF, and it sits in hue territory no competitor occupies.

*Known tension, accepted:* severity cannot be one set of hexes across both modes — the dark
values fail contrast on light (below). A brand element with two mode-dependent values is
weaker as a memory hook than a single colour. `docs/BRAND.md` records both sets as one
named scale so the intent survives.

### Light / dark / system theming

Three states: explicit light, explicit dark, and follow-the-OS (default).

**Token architecture.** `globals.css` currently hardcodes one dark palette on `:root`.
Restructure to:

```
:root                                          → light values (the default)
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"])              → dark values
}
:root[data-theme="dark"]                       → dark values (explicit override wins)
```

Every token gets a value on bare `:root`. No colour may be defined *only* inside a media
query or attribute selector, or the explicit toggle breaks in one direction.

**Light palette**, contrast measured against `--bg #f7f9fc`:

| Token | Light value | Ratio | |
|---|---|---|---|
| `--text` | `#0b1020` | 17.95:1 | AAA — the brand navy, doing double duty |
| `--muted` | `#55607d` | 5.93:1 | AA |
| `--accent` | `#1f4fd8` | 6.28:1 | AA |
| `--high` | `#c62828` | 5.33:1 | AA |
| `--medium` | `#8a5a00` | 5.62:1 | AA |
| `--low` | `#1a7f4b` | 4.76:1 | AA |
| `--line` | `#d9e2f0` | 1.24:1 | divider only — see below |

Reusing the dark tokens on light fails outright and must not be shortcut:
`--accent` 2.42:1, `--high` 2.78:1, `--medium` 1.76:1, `--low` 1.80:1 — all below the 3:1
floor, let alone 4.5:1.

`--line` at 1.24:1 is deliberate: it is a subtle divider, not a meaningful boundary, so
WCAG 1.4.11's 3:1 does not apply. If a border ever becomes the *only* thing separating two
interactive regions, that instance needs its own darker token.

**No flash of wrong theme.** Next.js renders HTML server-side before any JS runs, so a
theme read from `localStorage` on mount produces a visible flip on every load. A small
blocking inline script in `layout.tsx`'s `<head>` must set `data-theme` on `<html>` before
first paint. This is the single most likely thing to be got wrong.

**Persistence: `localStorage`, not the database.** Theme is a per-device display preference
and must apply before any network call resolves. Sub-project F may later mirror it to the
control plane as a per-user default, but the local value stays authoritative for first
paint.

**Control placement:** a three-state toggle (Light / Dark / System) in `Nav.tsx`. When F
ships a configuration page it can host a fuller version; the nav control remains.

**The logo has to swap with the theme.** Because the lockup is an `<img>` (decision above),
CSS cannot recolour it. `<picture>` with a `prefers-color-scheme` `media` attribute handles
the system case but **cannot see `data-theme`**, so it breaks under an explicit override.
Ship two `<img>` elements — `adwatch-logo-dark.svg` and `adwatch-logo-light.svg` — toggled
by the same CSS selectors that drive the palette. Both are already outlined.

### Remaining outlining

The logo lockups are done. Three mark files still contain live `<text>` (the small "Ad"
inside the tile) and carry the identical defect:

- `apps/web/public/mark.svg` — **in use today** in `Nav.tsx:41`
- `docs/brand/adwatch-mark.svg`
- `docs/brand/adwatch-mark-light.svg`

Same conversion, same glyph path already computed. Do these in the same pass.

## Verification

There is no web test suite — `apps/web/package.json` provides only `lint`, `typecheck`,
`build`. Verification is therefore explicit:

1. `npm run typecheck` — catches the moved import paths.
2. `npm run build` — catches route collisions and the redirect config.
3. `grep -rn '"/w/' apps services` returns nothing but the redirect rule.
4. `grep -c '<text' apps/web/public/logo.svg` → `0`.
5. Load `/watchlists`, `/watchlists/1`, and `/` against the running stack.
6. Load `/w/1` and confirm a 308 to `/watchlists/1`.
7. Trigger an alert and confirm the emitted `dashboard_url` contains `/watchlists/`.
8. Visual check: nav lockup against `docs/brand/adwatch-logo-dark.png` at 1x and 2x.

---

## Non-goals

This spec does **not** cover, and no part of it should be read as approving: the dashboard
page (D), LLM cost metering (B), the alerts read API (C), the configuration page (F), the
historical read API (G), snapshot retention (H), or the SerpApi health check (I).

---

## Open questions

1. **`/` interim behaviour** — redirect to `/watchlists` (specified above), or a minimal
   landing page? Redirect is assumed.
2. **Nav item count.** D will add "Dashboard", taking the bar to five items. Not a decision
   for this spec, but worth confirming five is acceptable before the layout is built around it.
3. **`docs/brand/adwatch-logo-light.svg`** has the same live-text defect and is used by
   nothing currently. Outline it too for consistency, or leave it?
