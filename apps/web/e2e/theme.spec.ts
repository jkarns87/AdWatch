import { expect, test } from "./fixtures";

const DARK_BG = "rgb(11, 16, 32)"; // --bg #0b1020
const LIGHT_BG = "rgb(247, 249, 252)"; // --bg #f7f9fc

const bodyBg = (page: import("@playwright/test").Page) =>
  page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test.describe("light / dark / system", () => {
  test("explicit dark paints the dark ground regardless of OS setting", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Dark" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await bodyBg(page)).toBe(DARK_BG);
  });

  test("explicit light wins even when the OS prefers dark", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Light" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    expect(await bodyBg(page)).toBe(LIGHT_BG);
  });

  test("system follows the OS and sets no attribute", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Dark" }).click();
    await page.getByRole("button", { name: "System" }).click();
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
    expect(await bodyBg(page)).toBe(DARK_BG); // OS is dark
  });

  test("the choice survives a reload", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Light" }).click();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    expect(await bodyBg(page)).toBe(LIGHT_BG);
  });

  test("no flash of the wrong theme on first paint", async ({ page }) => {
    // The blocking script in <head> must set data-theme before the body renders.
    // Reading the attribute at document_start proves it ran ahead of first paint
    // rather than on mount, which is what would produce a visible flip.
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Light" }).click();

    const attrAtStart: (string | null)[] = [];
    await page.addInitScript(() => {
      document.addEventListener("readystatechange", () => {
        (window as unknown as { __themeAtParse?: string | null }).__themeAtParse ??=
          document.documentElement.getAttribute("data-theme");
      });
    });
    await page.reload();
    attrAtStart.push(
      await page.evaluate(() => (window as unknown as { __themeAtParse?: string | null }).__themeAtParse ?? null)
    );
    expect(attrAtStart[0]).toBe("light");
  });

  test("the logo swaps with the theme, one visible at a time", async ({ page }) => {
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Dark" }).click();
    await expect(page.locator("img.logo-dark")).toBeVisible();
    await expect(page.locator("img.logo-light")).toBeHidden();

    await page.getByRole("button", { name: "Light" }).click();
    await expect(page.locator("img.logo-light")).toBeVisible();
    await expect(page.locator("img.logo-dark")).toBeHidden();
  });

  test("the primary button stays legible in light mode", async ({ page }) => {
    // .btn-primary hardcoded #0b1020 as its text colour, which is navy-on-dark-blue
    // once --accent becomes #1f4fd8. It shipped invisible-by-luck because light mode
    // did not exist yet.
    await page.goto("/watchlists");
    await page.getByRole("button", { name: "Light" }).click();
    const btn = page.locator(".btn-primary").first();
    await expect(btn).toBeVisible();
    const { color, background } = await btn.evaluate((el) => {
      const s = getComputedStyle(el);
      return { color: s.color, background: s.backgroundColor };
    });
    expect(color).toBe("rgb(255, 255, 255)"); // --on-accent
    expect(background).toBe("rgb(31, 79, 216)"); // --accent #1f4fd8
  });
});
