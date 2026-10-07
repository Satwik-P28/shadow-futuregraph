import { expect, test } from "@playwright/test";

test("saved futures show a typed cross-plan conflict", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "1 cross-plan conflict" })).toBeVisible();
  await page.getByRole("button", { name: "1 cross-plan conflict" }).click();
  const detail = page.getByLabel("Cross-plan detail");
  await expect(detail).toBeVisible();
  await expect(detail.getByText("These futures are individually valid but incompatible together.")).toBeVisible();
  await expect(detail.getByText("This plan works alone, but conflicts with another future.")).toBeVisible();
  await expect(detail.getByText("NYC airport window", { exact: true })).toBeVisible();
  await expect(detail.getByText("Gallery opening", { exact: true })).toBeVisible();
  await expect(detail.getByText(/Shared resource: alex/)).toBeVisible();
});
