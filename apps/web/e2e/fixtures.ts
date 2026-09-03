import { test as base } from "@playwright/test";

/**
 * The production build carries NEXT_PUBLIC_AUTH_PROVIDER=xano. Without a token,
 * lib/auth.ts sends no Authorization header, the API answers 401, and lib/api.ts
 * redirects the browser to /login. Pages therefore render and then navigate away
 * mid-assertion — which surfaces as non-deterministic "element not found" and
 * "toHaveURL" failures that look like flaky tests rather than an auth redirect.
 *
 * Seeding a token before page scripts run keeps every spec on the page it asked
 * for. The token is never validated client-side; data calls still 401 and those
 * views show their error panel, which is fine — these specs assert routing,
 * theming and form behaviour, not data.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("adwatch.xano.token", "e2e-fake-token");
    });
    await use(page);
  },
});

export { expect } from "@playwright/test";
