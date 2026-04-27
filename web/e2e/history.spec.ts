import { test, expect } from "@playwright/test";

test.describe("History screen", () => {
  test("shows empty state when no runs exist", async ({ page }) => {
    // Mock the runs API to return empty list
    await page.route("**/api/runs*", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: [], next_cursor: null }),
      });
    });

    await page.goto("/history");

    // Should show empty state
    await expect(page.getByTestId("empty-runs")).toBeVisible();
    await expect(page.getByText("No runs yet")).toBeVisible();
  });

  test("shows runs list when runs exist", async ({ page }) => {
    await page.route("**/api/runs*", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: [
            {
              id: "abc12345deadbeef",
              status: "done",
              kind: "analyze",
              started_at: "2025-01-15T10:30:00Z",
              completed_at: "2025-01-15T10:31:00Z",
              duration_ms: 60000,
              tickers: ["AAPL", "MSFT"],
              model_name: "gpt-4o",
              model_provider: "OpenAI",
            },
          ],
          next_cursor: null,
        }),
      });
    });

    await page.goto("/history");

    // Should show the runs table
    await expect(page.getByTestId("runs-table")).toBeVisible();
    await expect(page.getByText("AAPL, MSFT")).toBeVisible();
    await expect(page.getByText("gpt-4o")).toBeVisible();
    await expect(page.getByText("done")).toBeVisible();
  });
});
