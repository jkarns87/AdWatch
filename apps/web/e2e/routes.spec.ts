import { expect, test } from "./fixtures";

test.describe("watchlist routes", () => {
  test("/ is the dashboard, no longer a redirect", async ({ page }) => {
    // It redirected to /watchlists as an interim while the dashboard did not exist.
    await page.goto("/");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("/watchlists renders the list page", async ({ page }) => {
    await page.goto("/watchlists");
    await expect(page.getByRole("heading", { name: "Watchlists" })).toBeVisible();
  });

  test("the old /w/:id link still resolves", async ({ request }) => {
    // alert_log has already persisted /w/{id} links into Slack and Teams. Renaming the
    // route does not rewrite messages that were already delivered, so this redirect is
    // permanent and must not be removed.
    const res = await request.get("/w/1", { maxRedirects: 0 });
    expect(res.status()).toBe(308);
    expect(res.headers()["location"]).toBe("/watchlists/1");
  });

  test("a detail page loads under the new path", async ({ page }) => {
    await page.goto("/watchlists/1");
    await expect(page.locator("header")).toBeVisible();
  });

  test("the Watchlists nav tab is marked active on a detail page", async ({ page }) => {
    // Regression guard: the old predicate was p.startsWith("/w/"), and
    // "/watchlists/1".startsWith("/w/") is false — the tab silently stopped
    // highlighting with no error and no failing build.
    await page.goto("/watchlists/1");
    const tab = page.getByRole("link", { name: "Watchlists" });
    await expect(tab).toHaveAttribute("data-active", "true");
  });
});
