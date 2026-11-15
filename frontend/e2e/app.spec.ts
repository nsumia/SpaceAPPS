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
  await expect(page.getByTestId("summary")).toContainText("Burdur: the mean area of its last 3 valid years");
  await page.getByRole("button", { name: "Add to compare" }).click();
  await page.getByRole("link", { name: /Open compare/ }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByTestId("chosen")).toContainText("Burdur");
  await page.screenshot({ path: process.env.SHOT_COMPARE ?? "test-results/compare.png", fullPage: true });
});

test("expand button widens the side panel, charts follow, state is remembered, collapse restores", async ({ page }) => {
  await openMap(page);
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [30.17, 37.75], zoom: 6 }));
  await page.waitForTimeout(500);
  const p = await px(page, 30.17, 37.75);
  await page.mouse.click(p.x, p.y);
  const panel = page.getByTestId("panel");
  await expect(panel).toBeVisible({ timeout: 3000 });
  await expect(panel.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
  const w0 = (await panel.boundingBox())!.width;
  const c0 = (await panel.locator("canvas").first().boundingBox())!.width;
  await page.getByTestId("panel-expand").click();
  await expect.poll(async () => (await panel.boundingBox())!.width).toBeGreaterThan(w0 + 200);
  // echarts re-fitted: the canvas got wider (2-column layout) and still lies inside the panel
  await expect.poll(async () => (await panel.locator("canvas").first().boundingBox())?.width ?? 0, { timeout: 5000 }).toBeGreaterThan(c0 + 20);
  const pb = (await panel.boundingBox())!, cb = (await panel.locator("canvas").first().boundingBox())!;
  expect(cb.x + cb.width).toBeLessThanOrEqual(pb.x + pb.width + 1);
  expect(await page.evaluate(() => localStorage.getItem("panelLayout"))).toContain('"expanded":true');
  await expect(panel.getByTestId("chart-help").first()).toContainText("What this shows");
  await page.getByTestId("panel-expand").click();
  await expect.poll(async () => Math.abs((await panel.boundingBox())!.width - w0)).toBeLessThan(3);
  // drag handle resizes (desktop)
  const h = (await page.getByTestId("panel-resize").boundingBox())!;
  await page.mouse.move(h.x + 3, h.y + 200); await page.mouse.down(); await page.mouse.move(h.x - 150, h.y + 200, { steps: 6 }); await page.mouse.up();
  await expect.poll(async () => (await panel.boundingBox())!.width).toBeGreaterThan(w0 + 100);
});

test("compare scatter explains itself and lists lakes without data", async ({ page }) => {
  await page.goto("/compare");
  await expect(page.getByTestId("scatter-help")).toContainText("How to read");
  await expect(page.getByTestId("scatter-legend")).toContainText("hollow grey = climate share not computable");
  await expect(page.getByTestId("scatter-excluded")).toContainText("no Landsat 5 warming value");
  await expect(page.locator("table.rank th .info").first()).toBeVisible();
});

test("default basemap is NASA Blue Marble (GIBS tiles requested first); no unverified badge or 'Not computable' block", async ({ page }) => {
  const gibs: string[] = [];
  page.on("request", (r) => { if (/gibs\.earthdata/.test(r.url())) gibs.push(r.url()); });
  await openMap(page);
  expect(gibs.some((u) => u.includes("BlueMarble_ShadedRelief_Bathymetry"))).toBe(true);
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [30.17, 37.75], zoom: 6 }));
  await page.waitForTimeout(500);
  const p = await px(page, 30.17, 37.75);
  await page.mouse.click(p.x, p.y);
  await expect(page.getByTestId("panel")).toBeVisible({ timeout: 3000 });
  await expect(page.getByTestId("panel")).not.toContainText(/not checked against published data|Not computable|show the \(non-interpretable\)/);
});

test("top bar: brand, nav with aria-current, TR/EN switch, no overflow at 390 px", async ({ page }) => {
  await page.route(/openfreemap|gibs\.earthdata/, (r) => r.abort());
  await page.goto("/methods");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Methods" })).toHaveAttribute("aria-current", "page");
  await expect(nav.getByRole("link", { name: "Map" })).not.toHaveAttribute("aria-current", "page");
  expect((await page.locator("header.top").boundingBox())!.height).toBeLessThanOrEqual(60);
  await expect(page.locator(".brand-name")).toHaveText("Lake Loss Detective");
  await expect(page.locator(".brand-name")).toHaveCSS("font-family", /Roboto/);
  expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check('600 19px "Roboto Variable"'); })).toBe(true);
  await page.getByRole("button", { name: /Switch language/ }).click();
  await expect(page.locator(".brand-name")).toHaveText("Göl Kaybı Dedektifi");
  await expect(page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Yöntem" })).toHaveAttribute("aria-current", "page");
  await page.setViewportSize({ width: 390, height: 800 });
  const w = await page.evaluate(() => { const h = document.querySelector("header.top")!; return [h.scrollWidth, h.clientWidth]; });
  expect(w[0]).toBeLessThanOrEqual(w[1]);
  await page.reload();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "İçeriğe geç" })).toBeFocused();
});
