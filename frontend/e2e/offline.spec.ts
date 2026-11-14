import { expect, test, type Page } from "@playwright/test";

// Demo-offline acceptance: every request to a non-local host is aborted (browser side) and the backend runs with
// LLD_OFFLINE=1 (no outbound sockets). Live data comes from the committed demo cache (stale: true).
async function blockExternal(page: Page) {
  const external: string[] = [];
  await page.route((url) => !["127.0.0.1", "localhost"].includes(url.hostname), (r) => { external.push(r.request().url()); return r.abort(); });
  return external;
}
const px = (page: Page, lon: number, lat: number) =>
  page.evaluate(([x, y]) => { const m = (window as any).__map; const p = m.project([x, y]); const r = m.getCanvas().getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; }, [lon, lat]);

test("offline: local basemap, all lakes, cached live cards, compare, sample job", async ({ page }) => {
  const external = await blockExternal(page);
  await page.goto("/");
  await page.waitForFunction(() => {
    const m = (window as any).__map;
    return m && m.getLayer("lakes-circle") && m.querySourceFeatures("lakes").length >= 17;
  }, null, { timeout: 30_000 });
  // 1. automatic fallback to the local country-borders basemap
  await expect(page.getByTestId("offline-note")).toBeVisible();
  await page.waitForFunction(() => { const m = (window as any).__map; return m.getLayer("countries-line") && m.isSourceLoaded("countries"); }, null, { timeout: 15_000 });
  expect(await page.getByTestId("toolbar").locator("select").inputValue()).toBe("offline");
  // 2. Burdur panel with cached (stale) live cards
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [30.17, 37.75], zoom: 6 }));
  await page.waitForTimeout(500);
  const p = await px(page, 30.17, 37.75);
  await page.mouse.click(p.x, p.y);
  await expect(page.getByRole("heading", { name: "Burdur" })).toBeVisible({ timeout: 5000 });
  await expect(page.getByTestId("live-card").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("live-card").filter({ hasText: "Water area" }).getByTestId("cache-tag")).toBeVisible();
  await expect(page.getByTestId("live-card").filter({ hasText: "Water area" }).getByText("stale")).toBeVisible();
  await expect(page.getByTestId("live-card").filter({ hasText: "Water area" }).locator(".card-v b")).toHaveText(/\d/);
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.screenshot({ path: process.env.SHOT_OFFLINE ?? "test-results/offline-map.png" });
  // 2b. second lake (Van): cached snapshot image really loads offline
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [42.95, 38.65], zoom: 6 }));
  await page.waitForTimeout(500);
  const pv = await px(page, 42.95, 38.65);
  await page.mouse.click(pv.x, pv.y);
  await expect(page.getByRole("heading", { name: "Van" })).toBeVisible({ timeout: 5000 });
  const img = page.getByTestId("gibs-card").locator("img");
  await expect(img).toBeVisible({ timeout: 20_000 });
  await expect.poll(() => img.evaluate((e: HTMLImageElement) => e.complete && e.naturalWidth > 100), { timeout: 10_000 }).toBe(true);
  // 3. compare screen with two lakes
  await page.evaluate(() => localStorage.setItem("compare", JSON.stringify(["burdur", "van", "urmia"])));
  await page.goto("/compare");
  await expect(page.getByTestId("chosen")).toContainText("Burdur");
  await expect(page.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
  expect(await page.locator("table tbody tr").count()).toBeGreaterThanOrEqual(17);
  // 4. pre-computed sample job: progress -> done, labelled
  await page.goto("/");
  await page.getByTestId("sample-btn").click();
  await expect(page.getByTestId("sample-label")).toContainText("PRE-COMPUTED SAMPLE");
  await page.getByTestId("analyze").click();
  await expect(page.getByTestId("analysis-progress")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("analysis-progress")).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByTestId("summary")).toBeVisible();
  await expect(page.getByTestId("sample-label")).toBeVisible();
  expect(external.length).toBeGreaterThan(0);        // the page did try external hosts (basemap), all were blocked
});
