import { expect, test } from "./fixtures";

test.describe("API keys", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings/integrations");
  });

  test("shows a stored key by its last four characters only", async ({ page }) => {
    const section = page.getByTestId("api-keys");
    // useInnerText is the point: textContent ignores CSS text-transform, so without
    // it this passes even while the badge renders "••••AAAA". .badge uppercases by
    // default, which misrepresents case-sensitive key material.
    await expect(section).toContainText("••••aaaa", { useInnerText: true });
    await expect(section).not.toContainText("aaaaaaaa", { useInnerText: true });
  });

  test("a provider with no key of its own says so", async ({ page }) => {
    await expect(page.getByTestId("api-keys")).toContainText("platform key");
  });

  test("the input masks what you type", async ({ page }) => {
    const input = page.getByLabel("SerpApi API key");
    await expect(input).toHaveAttribute("type", "password");
    await expect(input).toHaveAttribute("autocomplete", "off");
  });

  test("saving reports that the provider verified the key", async ({ page }) => {
    // Scoped per provider: the page's "Add a destination" form also has a Save
    // button, and before the key list loads both providers render one too.
    const anthropic = page.getByTestId("key-anthropic");
    await page.getByLabel("Anthropic API key").fill("sk-ant-whatever");
    await anthropic.getByRole("button", { name: "Save" }).click();
    await expect(page.getByTestId("api-keys")).toContainText("verified with the provider");
  });

  test("save is disabled until something is typed", async ({ page }) => {
    await expect(page.getByTestId("key-anthropic").getByRole("button", { name: "Save" })).toBeDisabled();
  });

  test("a stored key offers Replace and Remove instead of Save", async ({ page }) => {
    const serpapi = page.getByTestId("key-serpapi");
    await expect(serpapi.getByRole("button", { name: "Replace" })).toBeVisible();
    await expect(serpapi.getByRole("button", { name: "Remove" })).toBeVisible();
  });
});
