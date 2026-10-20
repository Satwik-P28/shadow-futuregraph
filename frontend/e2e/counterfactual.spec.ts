import { expect, test } from "@playwright/test";

test("changing a modeled uncertainty re-evaluates the future", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "NYC trip" }).click();
  await page.getByRole("button", { name: "Analyze my future" }).click();
  await expect(page.getByRole("heading", { name: /future bug/ })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/256 actual evaluations per supported option/)).toBeVisible();
  await expect(page.getByText("Selected", { exact: true })).toBeVisible();
  const slider = page.getByRole("slider", { name: "Flight delay" });
  await expect(slider).toHaveAttribute("min", "0");
  await expect(slider).toHaveAttribute("max", "180");
  await page.getByRole("button", { name: "Original intention" }).click();
  await slider.fill("180");
  await expect(page.getByText("Evaluated path fails")).toBeVisible();
  await expect(page.getByText(/Violated:/)).toBeVisible();
  await page.getByRole("button", { name: "Return to approved state" }).click();
  await expect(page.getByText("Evaluated path fails")).toHaveCount(0);
});
