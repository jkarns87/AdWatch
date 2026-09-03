import { expect, test } from "./fixtures";

/** API responses come from e2e/fixtures.ts, so these assert rendered values rather
 *  than mere presence. */
test.describe("dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("shows the four cost and quota tiles", async ({ page }) => {
    // Scoped by test id: "Watchlists" and "Claude" also appear in the nav, and text
    // selectors would resolve to two elements.
    const tiles = page.getByTestId("kpi");
    await expect(tiles).toHaveCount(4);
    await expect(tiles.filter({ hasText: "SerpApi searches left" })).toBeVisible();
    await expect(tiles.filter({ hasText: "Cost this month" })).toBeVisible();
    await expect(tiles.filter({ hasText: "Claude calls" })).toBeVisible();
  });

  test("quota shows the plan allowance and granted credits separately", async ({ page }) => {
    // 14,370 against a 250/month plan would read as broken; the split is the point.
    const tile = page.getByTestId("kpi").filter({ hasText: "SerpApi searches left" });
    await expect(tile).toContainText("14,370");
    await expect(tile).toContainText("250 plan + 14,120 credits");
  });

  test("cost is split between SerpApi and Claude", async ({ page }) => {
    const tile = page.getByTestId("kpi").filter({ hasText: "Cost this month" });
    await expect(tile).toContainText("$1.38");
    await expect(tile).toContainText("$0.96 SerpApi");
    await expect(tile).toContainText("$0.42 Claude");
  });

  test("a valid key reads as valid, with its source", async ({ page }) => {
    const panel = page.getByTestId("provider-serpapi");
    await expect(panel).toContainText("Valid");
    await expect(panel).toContainText("Free Plan");
    await expect(panel).toContainText("key from platform");
  });

  test("an alert card shows severity, watchlist and delivery", async ({ page }) => {
    const card = page.getByRole("link", { name: /Blue Bottle/ });
    await expect(card).toContainText("high");
    await expect(card).toContainText("Specialty Coffee");
    await expect(card).toContainText("slack · sent");
  });

  test("the burn table totals SerpApi and Claude per watchlist", async ({ page }) => {
    const row = page.getByRole("row", { name: /Specialty Coffee/ });
    await expect(row).toContainText("57");      // searches
    await expect(row).toContainText("$0.57");   // 57 x rate
    await expect(row).toContainText("$0.42");   // claude
    await expect(row).toContainText("$0.99");   // total
  });

  test("shows both provider health panels", async ({ page }) => {
    await expect(page.getByTestId("provider-serpapi")).toBeVisible();
    await expect(page.getByTestId("provider-anthropic")).toBeVisible();
  });

  test("shows the alert and spend sections", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Recent alerts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Where the money goes" })).toBeVisible();
  });

  test("degrades to placeholders rather than crashing when the API is unreachable", async ({ page }) => {
    await page.route("**/api/v1/**", (route) => route.abort());
    await page.reload();
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    // em-dash placeholders, not "NaN" or "undefined"
    const body = await page.locator("body").innerText();
    expect(body).not.toContain("NaN");
    expect(body).not.toContain("undefined");
  });

  test("the Dashboard nav tab is active on /", async ({ page }) => {
    await expect(page.getByRole("link", { name: "Dashboard" })).toHaveAttribute("data-active", "true");
  });

  test("the Watchlists tab is not active on /", async ({ page }) => {
    await expect(page.getByRole("link", { name: "Watchlists", exact: true })).toHaveAttribute("data-active", "false");
  });
});
