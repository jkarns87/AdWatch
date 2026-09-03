// Capture Devpost screenshots from the DEPLOYED app (https://adwatch.dev), signed in
// as the demo account. Not a test — a one-shot capture script.
//
//   CAPTURE_EMAIL=... CAPTURE_PASSWORD=... node e2e/capture-screenshots.mjs
//
// Credentials come from the environment and are deliberately not defaulted here — this
// repo is public. Writes into ../../docs/screenshots/.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(HERE, '../../../docs/screenshots')
const BASE = process.env.CAPTURE_BASE ?? 'https://adwatch.dev'
const EMAIL = process.env.CAPTURE_EMAIL
const PASSWORD = process.env.CAPTURE_PASSWORD
if (!EMAIL || !PASSWORD) {
  console.error('set CAPTURE_EMAIL and CAPTURE_PASSWORD')
  process.exit(1)
}

const SHOTS = [
  ['01-dashboard', '/'],
  ['02-watchlists', '/watchlists'],
  // Detail path is discovered after sign-in — re-seeding the demo data changes the id.
  ['03-watchlist-detail', null],
  ['04-usage', '/usage'],
  ['05-alerts', '/alerts'],
  ['06-integrations', '/settings/integrations'],
  ['07-onboarding', '/onboarding'],
]

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()

console.log(`signing in at ${BASE}/login as ${EMAIL}`)
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
// The form labels its fields with placeholders, not <label>, so target by input type.
await page.locator('input[type="email"]').fill(EMAIL)
await page.locator('input[type="password"]').fill(PASSWORD)
await page.getByRole('button', { name: /^sign in$/i }).click()
await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30_000 })
console.log(`signed in, landed on ${new URL(page.url()).pathname}`)

// Find a real watchlist id rather than hardcoding one that re-seeding will invalidate.
await page.goto(`${BASE}/watchlists`, { waitUntil: 'networkidle' })
const detailPath = await page
  .locator('a[href^="/watchlists/"]')
  .first()
  .getAttribute('href')
console.log(`watchlist detail resolved to ${detailPath}`)

for (const [name, rawPath] of SHOTS) {
  const path = rawPath ?? detailPath
  if (!path) {
    console.log(`  SKIP ${name} — no watchlist found to link to`)
    continue
  }
  try {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle', timeout: 45_000 })
    // Give charts and any client-side fetch a beat to paint before capturing.
    await page.waitForTimeout(2500)
    const file = `${OUT}/${name}.png`
    await page.screenshot({ path: file, fullPage: true })
    console.log(`  ok   ${name.padEnd(22)} ${path}  ->  ${new URL(page.url()).pathname}`)
  } catch (err) {
    console.log(`  FAIL ${name.padEnd(22)} ${path}  ${err.message.split('\n')[0]}`)
  }
}

// Dark theme of the dashboard, to show theming.
try {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${OUT}/08-dashboard-dark.png`, fullPage: true })
  console.log('  ok   08-dashboard-dark')
} catch (err) {
  console.log(`  FAIL 08-dashboard-dark  ${err.message.split('\n')[0]}`)
}

await browser.close()
console.log(`\nwrote to ${OUT}`)
