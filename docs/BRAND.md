# AdWatch — brand reference

Everything here is load-bearing. The palette drives `.sev-*` badges, the change feed, and the
generated PDF/DOCX reports; the logo assets are shared between the web app and those reports.

---

## Position

**The navy ground is the signature, not the blue.**

`--bg #0b1020` is 49% saturated at 8% luminance — a blue-black. Measured against the
category (colours taken from each vendor's live homepage, converted to HSL), six of nine
markers sit between 210° and 240°:

| Vendor | Accent | Hue | Sat |
|---|---|---|---|
| Adbeat | `#43484d` | 210° | 7% — effectively greyscale |
| **AdWatch (dark)** | `#6ea8fe` | 216° | 99% |
| SpyFu | `#6c7483` | 219° | 10% — effectively greyscale |
| Similarweb | `#195afe` | 223° | 99% |
| **AdWatch (light)** | `#1f4fd8` | 224° | 75% |
| BigSpy | `#5a5af3` | 240° | 86% |
| Sensor Tower | `#00cfb8` | 173° | 100% |
| Foreplay | `#ffc852` | 41° | 100% |

`#1f4fd8` is **one degree of hue from Similarweb's `#195afe`** (ΔRGB 40). This is known and
accepted: the differentiator is the saturated dark ground, which nobody else in the set uses
(Sensor Tower's `#232325` is 3% saturated — a neutral black). Light mode therefore carries
the navy into the header, the mark tile, and body text.

**Severity is a brand element, not just a status scale.** The product is *what changed and
how badly*. The triple sits in hue territory no competitor occupies. It cannot be one set of
hexes across both modes — the dark values fail contrast on light — so it is defined below as
one named scale with two mode-dependent value sets.

---

## Palette

Defined in `apps/web/app/globals.css`. Three states: light (default), system-dark, explicit-dark.

| Token | Light | Ratio¹ | Dark | Ratio² |
|---|---|---|---|---|
| `--bg` | `#f7f9fc` | — | `#0b1020` | — |
| `--panel` | `#ffffff` | — | `#121a2e` | — |
| `--panel-2` | `#eef3fa` | — | `#182238` | — |
| `--line` | `#d9e2f0` | 1.24:1³ | `#24304d` | — |
| `--text` | `#0b1020` | 17.95:1 AAA | `#e6ebf5` | 15.84:1 AAA |
| `--muted` | `#55607d` | 5.93:1 AA | `#8b96b3` | 6.41:1 AA |
| `--accent` | `#1f4fd8` | 6.28:1 AA | `#6ea8fe` | 7.84:1 AAA |
| `--on-accent` | `#ffffff` | — | `#0b1020` | — |
| `--high` | `#c62828` | 5.33:1 AA | `#ff6b6b` | 6.82:1 AA |
| `--medium` | `#8a5a00` | 5.62:1 AA | `#ffb454` | 10.74:1 AAA |
| `--low` | `#1a7f4b` | 4.76:1 AA | `#7dd3a0` | 10.55:1 AAA |

¹ against `--bg #f7f9fc`  ² against `--bg #0b1020`
³ `--line` is a subtle divider, not a meaningful boundary, so WCAG 1.4.11's 3:1 does not
apply. If a border ever becomes the *only* separator between two interactive regions, that
instance needs its own darker token.

### Do not reuse dark tokens on light

They fail outright — all below the 3:1 floor, let alone 4.5:1:

```
--accent  #6ea8fe on white   2.42:1
--high    #ff6b6b on white   2.78:1
--medium  #ffb454 on white   1.76:1
--low     #7dd3a0 on white   1.80:1
```

### Rules

- **`--accent` is the logo stroke colour.** `#6ea8fe` appears in the eye swoosh and iris of
  every mark and lockup. Changing the token without re-exporting the assets desyncs the UI
  from the logo.
- **Every token needs a value on bare `:root`.** A colour defined only inside a media query
  or a `[data-theme]` selector breaks the toggle in one direction.
- **No hardcoded colour in `.tsx`.** Current count: 0. Keep it there. Tints use
  `color-mix(in srgb, var(--token) N%, transparent)` so they follow the theme.
- **`--on-accent` exists because `.btn-primary` needs readable text on the accent fill.**
  Hardcoding `#0b1020` there produced navy-on-dark-blue in light mode.

---

## Theming

`localStorage` key **`adwatch-theme`**: `"light"`, `"dark"`, or absent (= follow the OS).

Two places must stay in sync:

- `apps/web/app/layout.tsx` — a blocking inline `<script>` in `<head>` that sets
  `data-theme` **before first paint**. Without it every load flashes the wrong theme. It is
  deliberately not `async`/`defer`.
- `apps/web/components/ThemeToggle.tsx` — the three-state control that writes the key.

---

## Assets

| File | Used by |
|---|---|
| `apps/web/public/logo.svg` | nav lockup, dark theme |
| `apps/web/public/logo-light.svg` | nav lockup, light theme |
| `apps/web/public/mark.svg` | tile / square contexts |
| `apps/web/public/favicon.png`, `apple-touch-icon.png`, `icon-512.png` | browser + PWA icons |
| `services/api/app/reports/assets/logo-light.png` | PDF (`render_pdf.py`) and DOCX (`render_docx.py`) |
| `docs/brand/*` | source kit — dark/light lockups, marks, thumbnail |

The lockup cannot be recoloured by CSS (it is an `<img>`), so light and dark are two files
swapped by the `.logo-dark` / `.logo-light` rules in `globals.css`. `<picture>` with
`prefers-color-scheme` is **not** usable — it cannot see `data-theme`, so an explicit
override would show the wrong variant.

---

## The outlining constraint

**Every logo and mark SVG contains outlined paths, not `<text>`. Keep it that way.**

The wordmark is set in **Poppins Bold** (OFL 1.1). An SVG loaded through `<img src>` renders
in an isolated document and **cannot fetch webfonts** — it falls back to a locally installed
face. Poppins is not installed on a typical machine, so live `<text>` silently rendered the
wordmark in Helvetica everywhere, while the reports (raster PNG, type baked in) rendered it
correctly. Three different renderings of one wordmark shipped simultaneously.

Re-exporting any of these from a design tool with live text reintroduces the bug, and it is
invisible on any machine that happens to have Poppins installed locally.

Assert before committing a logo change:

```bash
grep -c '<text' apps/web/public/*.svg docs/brand/*.svg   # every file must report 0
```
