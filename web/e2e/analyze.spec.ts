import { test, expect } from "@playwright/test";

/**
 * Mock SSE helper: intercepts POST /api/runs/stream and returns
 * synthetic run.started → run.done events.
 */
async function mockSSE(page: import("@playwright/test").Page) {
  await page.route("**/api/runs/stream", async (route) => {
    const runId = "abc12345deadbeef";
    const events = [
      `event: run.started\ndata: ${JSON.stringify({ run_id: runId, status: "running" })}\n\n`,
      `event: run.done\ndata: ${JSON.stringify({
        run_id: runId,
        status: "done",
        decisions: {
          AAPL: { action: "buy", quantity: 100, confidence: 85.0, reasoning: "Strong fundamentals" },
          MSFT: { action: "hold", quantity: 0, confidence: 60.0, reasoning: "Fair value" },
        },
      })}\n\n`,
    ];

    const body = events.join("");
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      body,
    });
  });
}

test.describe("Analyze screen", () => {
  test("fills form, submits, and shows SSE results", async ({ page }) => {
    await mockSSE(page);

    await page.goto("/analyze");

    // The form should be visible
    await expect(page.locator("#tickers")).toBeVisible();
    await expect(page.getByRole("button", { name: /run analysis/i })).toBeVisible();

    // Clear default tickers and type new ones
    await page.locator("#tickers").fill("AAPL, MSFT");

    // Submit the form
    await page.getByRole("button", { name: /run analysis/i }).click();

    // Should show the running state then transition to done
    // Wait for decisions table to appear
    await expect(page.getByTestId("decisions-table")).toBeVisible({ timeout: 5000 });

    // Verify decisions rendered
    await expect(page.getByText("AAPL")).toBeVisible();
    await expect(page.getByText("buy")).toBeVisible();
    await expect(page.getByText("MSFT")).toBeVisible();
    await expect(page.getByText("hold")).toBeVisible();

    // Status should show "done"
    await expect(page.getByTestId("run-status")).toContainText("done");
  });

  test("shows error state on SSE error", async ({ page }) => {
    await page.route("**/api/runs/stream", async (route) => {
      const events = [
        `event: run.started\ndata: ${JSON.stringify({ run_id: "err123", status: "running" })}\n\n`,
        `event: error\ndata: ${JSON.stringify({ message: "LLM API key not configured", retryable: false })}\n\n`,
      ];
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: events.join(""),
      });
    });

    await page.goto("/analyze");
    await page.locator("#tickers").fill("AAPL");
    await page.getByRole("button", { name: /run analysis/i }).click();

    // Should show error message
    await expect(page.getByText("LLM API key not configured")).toBeVisible({ timeout: 5000 });
  });
});
