import { expect, test } from "@playwright/test";

test("sandbox hero finds a failure, approves, executes, and reacts to an injection", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "NYC trip" }).click();
  await expect(page.getByLabel("What are you planning?")).toHaveValue(
    "Move my NYC trip to Friday and make sure everything still works.",
  );
  await page.getByRole("button", { name: "Analyze my future" }).click();
  await expect(page.getByRole("heading", { name: /future bug/ })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Approve repaired future" }).click();
  await expect(page.getByText("Repaired future approved.")).toBeVisible();
  await page.getByRole("button", { name: "Execute sandbox actions" }).click();
  await expect(page.getByText("Observed state matches approved future")).toBeVisible();
  await page.getByRole("button", { name: "Try unrelated change" }).click();
  await expect(page.getByText("Blocked: action is outside the approved future.")).toBeVisible();
  await expect(page.getByText("Dinner is protected")).toBeVisible();
  await expect(page.getByLabel("Shadow Watch")).toContainText("Monitoring 1 approved future");
  await page.getByRole("button", { name: "+74 min delay" }).click();
  await expect(page.getByText(/assumption changed/i)).toBeVisible();
  await expect(page.getByText("Approved future still valid")).toBeVisible();
  await page.getByRole("button", { name: "Fare +$80" }).click();
  await expect(page.getByText("Approved future is no longer valid")).toBeVisible();
  await expect(page.getByText("Authority revoked")).toBeVisible();
});
