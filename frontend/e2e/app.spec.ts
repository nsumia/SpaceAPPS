import { expect, test, type Page } from "@playwright/test";

// External tile servers are blocked so the run is deterministic/offline: the app falls back to the plain basemap.
async function openMap(page: Page) {
  await page.route(/openfreemap|gibs\.earthdata/, (r) => r.abort());
  await page.route("**/api/lakes/*/live", (r) => r.fulfill({ json: { lake_id: "burdur", name: "Burdur", stale: false, generated_utc: "x", cards: {
    landsat: { source: "Landsat C2 L2", ok: true, cached: true, stale: false, age_s: 5, area_km2: 120.5, latest_scene: "2026-11-01", lst_c: 12, change_vs_last_year_pct: -1 },
    swot: { source: "SWOT", ok: false, error: "no pld", cached: false, stale: false, age_s: 0 },
    precip: { source: "NASA POWER", ok: true, cached: true, stale: false, age_s: 5, precip_mm: 200, pct_of_normal: 90, data_until: "2026-11-12" } } } }));
  await page.goto("/");
  await page.waitForFunction(() => {
    const m = (window as any).__map;
    return m && m.getLayer("lakes-circle") && m.querySourceFeatures("lakes").length >= 4;
  }, null, { timeout: 30_000 });
}

const px = (page: Page, lon: number, lat: number) =>
  page.evaluate(([x, y]) => { const m = (window as any).__map; const p = m.project([x, y]); const r = m.getCanvas().getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; }, [lon, lat]);

test("map -> click Burdur -> panel within 2 s -> add to compare", async ({ page }) => {
  await openMap(page);
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [30.17, 37.75], zoom: 6 }));
  await page.waitForTimeout(500);
  const p = await px(page, 30.17, 37.75);
  const t0 = Date.now();
  await page.mouse.click(p.x, p.y);
  await expect(page.getByTestId("panel")).toBeVisible({ timeout: 2000 });
  await expect(page.getByRole("heading", { name: "Burdur" })).toBeVisible({ timeout: 2000 });
  expect(Date.now() - t0).toBeLessThan(2000);
  await expect(page.getByTestId("summary")).toContainText("Burdur has lost");
  await page.getByRole("button", { name: "Add to compare" }).click();
  await page.getByRole("link", { name: /Open compare/ }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByTestId("chosen")).toContainText("Burdur");
  await page.screenshot({ path: process.env.SHOT_COMPARE ?? "test-results/compare.png", fullPage: true });
});

test("drawn rectangle starts an analysis job with visible progress (API mocked)", async ({ page }) => {
  let polls = 0;
  await page.route("**/api/analyze", (r) => r.fulfill({ status: 202, json: { job_id: "j1", lake_id: "custom-abc", status: "queued", progress: 0, current_year: null, phase: null, error: null, result_url: "", area_km2: 900 } }));
  await page.route("**/api/jobs/j1", (r) => r.fulfill({ json: { job_id: "j1", lake_id: "custom-abc", status: "running", progress: 20 + 15 * polls++, current_year: 1990 + 5 * polls, phase: "preliminary (every 5th year)", error: null, result_url: "" } }));
  await openMap(page);
  await page.getByTestId("draw-rect").click();
  const a = await px(page, 31.5, 40.2), b = await px(page, 32.2, 39.6);
  await page.mouse.click(a.x, a.y);
  await page.mouse.move(b.x, b.y, { steps: 5 });
  await page.mouse.click(b.x, b.y);
  await page.getByTestId("analyze").click();
  const bar = page.getByTestId("analysis-progress");
  await expect(bar).toBeVisible();
  await expect(bar).toContainText(/year: \d{4}/);
  await expect(bar.getByRole("progressbar")).toHaveAttribute("aria-valuenow", /\d+/);
});

test("analyze shows the backend 422 message for oversized areas", async ({ page }) => {
  await page.route("**/api/analyze", (r) => r.fulfill({ status: 422, json: { detail: "area of 52,000 km2 is larger than the 20,000 km2 limit: please select a smaller area around the lake" } }));
  await openMap(page);
  await page.getByTestId("draw-rect").click();
  const a = await px(page, 31, 41), b = await px(page, 33, 39);
  await page.mouse.click(a.x, a.y); await page.mouse.move(b.x, b.y, { steps: 5 }); await page.mouse.click(b.x, b.y);
  await page.getByTestId("analyze").click();
  await expect(page.getByRole("alert")).toContainText("20,000 km2");
});
