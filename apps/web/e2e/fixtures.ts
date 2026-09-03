import { test as base } from "@playwright/test";

/**
 * Two things every spec needs.
 *
 * 1. A token. The build carries NEXT_PUBLIC_AUTH_PROVIDER=xano, so without one
 *    lib/auth.ts sends no Authorization header.
 *
 * 2. Stubbed API responses. A seeded token is still not a *valid* token — the real
 *    API answers 401 and lib/api.ts redirects the browser to /login. Pages then
 *    render and navigate away mid-assertion, so a spec either flakes or, worse,
 *    passes by asserting before the redirect lands. Serving fixtures makes the
 *    specs deterministic and removes the dependency on a running backend, which is
 *    what CI has.
 *
 * These specs cover routing, theming and layout. Data correctness is covered by the
 * API's own tests.
 */

const USAGE = {
  workspace_id: 1,
  plan: "team",
  period_start: "2026-09-01T00:00:00Z",
  period_end: "2026-09-02T00:00:00Z",
  searches_used: 96,
  searches_budget: 3000,
  searches_remaining: 2904,
  budget_used_pct: 3.2,
  runs: 4,
  cost_to_date_usd: 0.96,
  projected_month_current_cadence: 570,
  projected_month_plan_cadence: 380,
  projected_cost_current_usd: 5.7,
  projected_cost_plan_usd: 3.8,
  rate_per_search_usd: 0.01,
  watchlists_used: 2,
  watchlists_limit: 10,
  by_watchlist: [
    {
      watchlist_id: 1, name: "Specialty Coffee — Bay Area", competitors: 4, keywords: 5,
      searches_used: 57, runs: 3, last_run_at: "2026-09-02T18:04:11Z", searches_per_run: 19,
      projected_month_current: 380, projected_month_plan: 190, over_plan_limits: false,
      llm_cost_usd: 0.42,
    },
  ],
  plans: [],
  llm: {
    calls: 12, cost_usd: 0.42, unpriced_calls: 0,
    input_tokens: 184000, output_tokens: 21000, cache_read_tokens: 0, cache_write_tokens: 0,
    by_feature: [{ feature: "analyst", calls: 10, cost_usd: 0.31 }, { feature: "report", calls: 2, cost_usd: 0.11 }],
    by_model: [{ model: "claude-sonnet-5", calls: 12, cost_usd: 0.42 }],
    metering_since: "2026-09-02T12:00:00Z",
  },
  total_cost_usd: 1.38,
};

const SERPAPI = {
  status: "ok", key_source: "platform", plan: "Free Plan",
  searches_left: 14370, plan_searches_left: 250, extra_credits: 14120,
  searches_per_month: 250, used_this_month: 0, cached: false,
};

const ALERTS = [
  {
    id: 31, watchlist_id: 1, watchlist_name: "Specialty Coffee — Bay Area",
    severity: "high", summary: "Blue Bottle launched four video creatives",
    why_it_matters: "…", created_at: "2026-09-02T18:04:11Z",
    delivery: { channel: "slack", status: "sent", target: "https://hooks.slack.invalid/services/T04…/B07…/***", sent_at: "2026-09-02T18:04:12Z", error: null },
  },
];

const WATCHLISTS = [
  {
    id: 1, name: "Specialty Coffee — Bay Area", vertical: "specialty coffee", geo: "US",
    competitor_count: 4, keyword_count: 5, last_run_at: "2026-09-02T18:04:11Z", open_changes: 7,
  },
];

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("adwatch.xano.token", "e2e-fake-token");
    });

    const FIXTURES: Record<string, unknown> = {
      "/usage": USAGE,
      "/providers/serpapi": SERPAPI,
      "/alerts": ALERTS,
      "/watchlists": WATCHLISTS,
      "/health": { status: "ok", db: "ok", serpapi_key_present: true, anthropic_key_present: true },
      "/workspace/keys": [{ kind: "serpapi", last4: "aaaa", created_at: "2026-09-02T12:00:00Z", updated_at: "2026-09-02T12:00:00Z" }],
    };

    // The control plane too. Nav calls xano.me() and xano.alerts() on mount, and
    // lib/xano.ts does window.location.href = "/login" when either fails. Against the
    // real Xano instance with a fake token that is a 401, so a global redirect fires a
    // few hundred milliseconds into *every* page — which is what made the suite flake
    // one run in three and what put the sign-in page in a dashboard screenshot.
    const XANO: Record<string, unknown> = {
      "/auth/me": {
        id: 1, name: "E2E", email: "e2e@example.invalid", workspace_id: 1, role: "owner",
        workspace: { id: 1, name: "Acme", plan: "team" },
      },
      "/alerts": { alerts: [], unread: 0 },
      "/auth/forgot_password": { ok: true, message: "If that address has an account, a reset link is on its way." },
      "/auth/reset_password": { ok: true, message: "Your password has been changed." },
    };

    // /watchlists/{id} needs its own match: it does not end with "/watchlists", and
    // falling through to [] leaves the detail page with nothing to render.
    const DETAIL = {
      id: 1, name: "Specialty Coffee — Bay Area", vertical: "specialty coffee", geo: "US",
      location: "San Francisco, California, United States", created_at: "2026-09-01T00:00:00Z",
      competitors: [{ id: 11, name: "Blue Bottle", domain: "bluebottlecoffee.com", advertiser_id: null, active_creatives: 14 }],
      keywords: [{ id: 21, term: "coffee subscription" }],
      last_run: { id: 3, started_at: "2026-09-02T18:00:00Z", finished_at: "2026-09-02T18:04:11Z", status: "done", searches_used: 19 },
    };

    const serve = (table: Record<string, unknown>) => async (route: import("@playwright/test").Route) => {
      const { pathname } = new URL(route.request().url());
      const match = Object.keys(table).find((suffix) => pathname.endsWith(suffix));
      const method = route.request().method();
      // PUT /workspace/keys/{kind} answers with the save result, not the list.
      if (method === "PUT" && /\/workspace\/keys\/\w+$/.test(pathname)) {
        const kind = pathname.split("/").pop();
        await route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({ kind, last4: "zzzz", verified: true }),
        });
        return;
      }
      if (method === "DELETE") {
        await route.fulfill({ status: 204, body: "" });
        return;
      }

      let body: unknown = match ? table[match] : [];
      if (!match && /\/watchlists\/\d+$/.test(pathname)) body = DETAIL;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    };

    await page.route("**/api/v1/**", serve(FIXTURES));
    await page.route("**/api:adwatch-control/**", serve(XANO));

    await use(page);
  },
});

export { expect } from "@playwright/test";
