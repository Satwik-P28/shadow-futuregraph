import { expect, test } from "@playwright/test";

test("future lab shows the nearest discovered failure without executing it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "NYC trip" }).click();
  await page.getByRole("button", { name: "Analyze my future" }).click();
  await expect(page.getByRole("heading", { name: /future bug/ })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Find nearest failure" }).click();
  await expect(page.getByText("This is the nearest failure Shadow discovered under the modeled ranges.")).toBeVisible();
  await expect(page.getByText("Simulation. This does not change the approved future or execute anything.")).toBeVisible();
});
