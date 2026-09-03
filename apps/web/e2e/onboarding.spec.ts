import { expect, test } from "./fixtures";

test.describe("new watchlist wizard", () => {
  test("the name field keeps focus while typing", async ({ page }) => {
    // Regression guard. Field was declared inside the Onboarding component body, so
    // every render produced a new function identity; React compared element types by
    // reference, saw a different component, and remounted the subtree — destroying the
    // input and its focus after a single keystroke. A unit test cannot catch this.
    await page.goto("/onboarding");
    const name = page.getByPlaceholder("e.g. Specialty Coffee — Bay Area");
    await expect(name).toBeEditable();
    await name.click();
    await expect(name).toBeFocused(); // hydration settled, focus actually took

    // keyboard.type targets whatever holds focus rather than a captured element
    // handle, so a remount shows up as a short value instead of a detached-node
    // error. Character by character, because the bug drops focus per keystroke.
    for (const ch of "Specialty Coffee") {
      await page.keyboard.type(ch);
    }

    await expect(name).toHaveValue("Specialty Coffee");
    await expect(name).toBeFocused();
  });

  test("every text field on step one survives multi-character input", async ({ page }) => {
    await page.goto("/onboarding");

    const geo = page.locator("input").nth(1);
    await geo.click();
    await geo.fill("");
    await geo.pressSequentially("GB", { delay: 20 });
    await expect(geo).toBeFocused();
    await expect(geo).toHaveValue("GB");

    const location = page.locator("input").nth(2);
    await location.click();
    await location.fill("");
    await location.pressSequentially("London", { delay: 20 });
    await expect(location).toBeFocused();
    await expect(location).toHaveValue("London");
  });

  test("the wizard advances to competitors", async ({ page }) => {
    await page.goto("/onboarding");
    await page.getByRole("button", { name: "Next: competitors" }).click();
    await expect(page.getByRole("heading", { name: "Who are the competitors?" })).toBeVisible();
  });
});
