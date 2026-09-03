import { expect, test } from "./fixtures";

test.describe("password reset", () => {
  test("sign in offers a way out when you cannot", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("link", { name: "Forgot your password?" })).toBeVisible();
  });

  test("the confirmation does not reveal whether the address exists", async ({ page }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill("nobody@example.invalid");
    await page.getByRole("button", { name: "Send reset link" }).click();

    const body = page.locator("main");
    await expect(body).toContainText("If that address has an account");
    // Anything definite here would turn the form into an account-enumeration oracle.
    await expect(body).not.toContainText("not found");
    await expect(body).not.toContainText("no account");
    await expect(body).not.toContainText("sent to nobody@example.invalid");
  });

  test("send is disabled until an address is entered", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.getByRole("button", { name: "Send reset link" })).toBeDisabled();
  });

  test("a link with no token says so instead of failing silently", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(page.locator("main")).toContainText("missing its token");
    await expect(page.getByRole("link", { name: "Request a new one" })).toBeVisible();
  });

  test("the app nav is hidden from a signed-out visitor", async ({ page }) => {
    await page.goto("/reset-password?token=sel.ver");
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeHidden();
    await expect(page.getByRole("link", { name: "Integrations" })).toBeHidden();
  });

  test("both password fields are masked", async ({ page }) => {
    await page.goto("/reset-password?token=sel.ver");
    await expect(page.getByLabel("New password", { exact: true })).toHaveAttribute("type", "password");
    await expect(page.getByLabel("Confirm new password")).toHaveAttribute("type", "password");
  });

  test("mismatched passwords block submission", async ({ page }) => {
    await page.goto("/reset-password?token=sel.ver");
    await page.getByLabel("New password", { exact: true }).fill("correcthorse");
    await page.getByLabel("Confirm new password").fill("batterystaple");
    await expect(page.locator("main")).toContainText("do not match");
    await expect(page.getByRole("button", { name: "Set new password" })).toBeDisabled();
  });

  test("a short password is refused before it reaches the API", async ({ page }) => {
    await page.goto("/reset-password?token=sel.ver");
    await page.getByLabel("New password", { exact: true }).fill("short");
    await expect(page.locator("main")).toContainText("At least 8 characters");
    await expect(page.getByRole("button", { name: "Set new password" })).toBeDisabled();
  });

  test("a valid reset confirms and sends you to sign in", async ({ page }) => {
    await page.goto("/reset-password?token=sel.ver");
    await page.getByLabel("New password", { exact: true }).fill("correcthorsebattery");
    await page.getByLabel("Confirm new password").fill("correcthorsebattery");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.locator("main")).toContainText("password has been changed");
  });
});
