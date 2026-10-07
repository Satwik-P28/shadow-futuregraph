import { expect, test } from "@playwright/test";

test("freeform text is not turned into a demo future", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("What are you planning?").fill("Should I marry this person?");
  await page.getByRole("button", { name: "Analyze my future" }).click();
  await expect(page.getByText("I don't have enough grounded information or executable structure to model this as a future.")).toBeVisible();
  await expect(page.getByText("I can still help identify considerations, but I won't pretend to simulate it.")).toBeVisible();
  await expect(page.getByRole("heading", { name: /future bug/ })).toHaveCount(0);
});

test("a schedule request without records asks for the missing information", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("What are you planning?").fill("Move my dentist appointment to Thursday without interfering with class.");
  await page.getByRole("button", { name: "Analyze my future" }).click();
  await expect(page.getByText("Missing information")).toBeVisible();
  await expect(page.getByText("the calendar record for the event you want to move")).toBeVisible();
  await expect(page.getByRole("heading", { name: /future bug/ })).toHaveCount(0);
});
