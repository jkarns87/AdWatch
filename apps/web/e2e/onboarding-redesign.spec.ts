import { expect, test } from "./fixtures";

test.describe("onboarding", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/onboarding");
  });

  test("text fields keep focus while typing", async ({ page }) => {
    // Ported from the wizard this page replaced. Field was declared inside the
    // component body there, so every render gave it a new identity and React
    // remounted the subtree, dropping focus after one keystroke. The new page does
    // not use that pattern, but the same mistake is easy to reintroduce and no unit
    // test can catch it.
    const name = page.getByLabel("Company name");
    await expect(name).toBeEditable();
    await name.click();
    await expect(name).toBeFocused();
    for (const ch of "Verve Coffee") await page.keyboard.type(ch);
    await expect(name).toHaveValue("Verve Coffee");
    await expect(name).toBeFocused();

    const site = page.getByLabel("Website");
    await site.click();
    for (const ch of "vervecoffee.com") await page.keyboard.type(ch);
    await expect(site).toHaveValue("vervecoffee.com");
    await expect(site).toBeFocused();
  });

  test("asks for three things, not a vertical from a list", async ({ page }) => {
    const form = page.getByTestId("onboarding-form");
    await expect(form.getByLabel("Company name")).toBeVisible();
    await expect(form.getByLabel("Website")).toBeVisible();
    await expect(form.getByLabel("What you sell")).toBeVisible();
    await expect(form).toContainText("costs no SerpApi quota");
  });

  test("analyse is disabled until name and website are given", async ({ page }) => {
    const btn = page.getByRole("button", { name: "Analyse my site" });
    await expect(btn).toBeDisabled();
    await page.getByLabel("Company name").fill("Verve");
    await expect(btn).toBeDisabled();
    await page.getByLabel("Website").fill("vervecoffee.com");
    await expect(btn).toBeEnabled();
  });

  async function analyse(page: import("@playwright/test").Page) {
    await page.getByLabel("Company name").fill("Verve Coffee");
    await page.getByLabel("Website").fill("vervecoffee.com");
    await page.getByLabel("What you sell").fill("DTC specialty roaster");
    await page.getByRole("button", { name: "Analyse my site" }).click();
    await expect(page.getByTestId("onboarding-review")).toBeVisible();
  }

  test("the review screen shows what was found", async ({ page }) => {
    await analyse(page);
    await expect(page.getByTestId("vertical-picker")).toContainText("Food & Drink");
    await expect(page.getByLabel("Keywords")).toHaveValue(/coffee subscription/);
    await expect(page.getByTestId("competitor-review")).toContainText("bluebottlecoffee.com");
  });

  test("your own domain is pinned and cannot be unchecked", async ({ page }) => {
    await analyse(page);
    const own = page.getByLabel("Your own domain");
    await expect(own).toBeChecked();
    await expect(own).toBeDisabled();
    await expect(page.getByTestId("competitor-review")).toContainText("you");
  });

  test("competitors start checked, and the search cost is stated", async ({ page }) => {
    await analyse(page);
    await expect(page.getByLabel("bluebottlecoffee.com")).toBeChecked();
    await expect(page.getByLabel("sightglasscoffee.com")).toBeChecked();
    await expect(page.getByTestId("onboarding-review")).toContainText("2 searches to verify");
  });

  test("unchecking one lowers the stated cost", async ({ page }) => {
    await analyse(page);
    await page.getByLabel("sightglasscoffee.com").uncheck();
    await expect(page.getByTestId("onboarding-review")).toContainText("1 search to verify");
  });

  test("the vertical can be overridden", async ({ page }) => {
    await analyse(page);
    await page.getByTestId("vertical-picker").getByRole("button", { name: "change" }).click();
    await page.getByLabel("Search verticals").fill("coffee");
    await page.getByRole("button", { name: "Coffee & Tea" }).click();
    await expect(page.getByTestId("vertical-picker")).toContainText("Coffee & Tea");
  });

  test("creating goes through to the new watchlist", async ({ page }) => {
    await analyse(page);
    await page.getByRole("button", { name: "Create watchlist" }).click();
    await expect(page).toHaveURL(/\/watchlists\/1$/);
  });
});
