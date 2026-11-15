import { expect, test, type Page } from "@playwright/test";

// External tile servers are blocked so the run is deterministic/offline: the app falls back to the plain basemap.
async function openMap(page: Page) {
  await page.route(/openfreemap|gibs\.earthdata/, (r) => r.abort());
  await page.route("**/api/lakes/*/live", (r) => r.fulfill({ json: { lake_id: "burdur", name: "Burdur", stale: false, generated_utc: "x", cards: {
    landsat: { source: "Landsat C2 L2", ok: true, cached: true, stale: false, age_s: 5, area_km2: 120.5, latest_scene: "2026-11-01", lst_c: 12, change_vs_last_year_pct: -1 },
        precip: { source: "NASA POWER", ok: true, cached: true, stale: false, age_s: 5, precip_mm: 200, pct_of_normal: 90, data_until: "2026-11-12" } } } }));
  await page.goto("/");
  await page.waitForFunction(() => {
    const m = (window as any).__map;
    return m && m.getLayer("lakes-circle") && m.querySourceFeatures("lakes").length >= 4;
  }, null, { timeout: 30_000 });
}

const px = (page: Page, lon: number, lat: number) =>
  page.evaluate(([x, y]) => { const m = (window as any).__map; const p = m.project([x, y]); const r = m.getCanvas().getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; }, [lon, lat]);

test("map: one spectrum legend (shrinking / growing) and data-driven dot colours", async ({ page }) => {
  await openMap(page);
  await expect(page.getByTestId("legend")).toHaveCount(1);
  await expect(page.getByTestId("legend")).toContainText("shrinking");
  await expect(page.getByTestId("legend")).toContainText("growing");
  await expect(page.getByTestId("spectrum")).toBeVisible();
  const ex = await page.evaluate(() => (window as any).__map.getPaintProperty("lakes-circle", "circle-color"));
  expect(ex[0]).toBe("case"); expect(ex[2][0]).toBe("interpolate");
  const feats = await page.evaluate(() => (window as any).__map.querySourceFeatures("lakes").map((f: any) => f.properties));
  expect(feats.some((f: any) => typeof f.trend === "number" && f.trend < 0)).toBe(true);
  expect(feats.every((f: any) => f.trend === undefined || Math.abs(f.trend) <= 20)).toBe(true);
});

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
  const panel0 = page.getByTestId("panel");
  await expect(panel0.locator(".badges, .badge")).toHaveCount(0);
  for (const re of [/validated against published data/i, /^reliable$/i, /reliability unknown/i, /How much water is stored/i, /No SWOT Prior Lake/i, /volume change/i, /SWOT water level/i, /no pld/i])
    await expect(panel0.getByText(re)).toHaveCount(0);
  await expect(page.getByTestId("panel").getByText(/A forecast, not a fact|jump by more than|are NOT reliable/)).toHaveCount(0);
  await page.getByRole("button", { name: "Add to compare" }).click();
  await page.getByRole("link", { name: /Open compare/ }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByTestId("chosen")).toContainText("Burdur");
  await expect(page.getByTestId("chosen")).not.toContainText("★");
  await expect(page.locator("tbody")).not.toContainText("★");
  // owner request 2026-11-15: no Turkish/reference distinction (this replaced the ".tr-lake" bold-name check)
  await expect(page.locator(".rank tr.tr-lake")).toHaveCount(0);
  await expect(page.getByTestId("group-filter")).toHaveCount(0);
  await expect(page.locator(".page.compare")).not.toContainText(/Turkish|Reference|Group/);
  expect(await page.locator(".chip").first().evaluate((e) => getComputedStyle(e).borderLeftWidth)).toBe("0px");
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
  await page.goto("/about");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "About" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "About", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: /limitations/i })).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Project summary", "How to read this app"]);
  await expect(page.getByRole("heading", { name: /glossary|data sources|validation/i })).toHaveCount(0);
  await expect(page.locator("main, .page").getByText(/^Metalimnion is a visual analysis app which simplifies/)).toBeVisible();
  await expect(page.getByText("Report Summary")).toHaveCount(0);
  expect(await page.locator(".brand-name").evaluate((e) => getComputedStyle(e).textTransform)).toBe("none");
  await expect(page.locator(".brand-name")).toHaveText("Metalimnion");
  await expect(page).toHaveTitle("Metalimnion");
  expect(await nav.getByRole("link", { name: "About" }).evaluate((e) => getComputedStyle(e).borderBottomWidth)).toBe("0px");
  await expect(nav.getByRole("link", { name: "Map" })).not.toHaveAttribute("aria-current", "page");
  expect((await page.locator("header.top").boundingBox())!.height).toBeLessThanOrEqual(60);
  await expect(page.locator(".brand-name")).toHaveText("Metalimnion");
  await expect(page.locator(".brand-name")).toHaveCSS("font-family", /Franklin/);
  expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check('600 19px "Libre Franklin Variable"'); })).toBe(true);
  const logo = page.locator("img.brand-logo");
  await expect(logo).toHaveAttribute("alt", "Augmented 6th");
  expect(await logo.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth)).toBeGreaterThan(0);
  expect((await page.request.get("/favicon-32.png")).status()).toBe(200);
  await page.getByRole("button", { name: /Switch language/ }).click();
  await expect(page.locator(".brand-name")).toHaveText("Metalimnion");
  await expect(page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Hakkında" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Proje özeti", "Bu uygulama nasıl okunur"]);
  await expect(page.getByText(/^Metalimnion, dünya genelindeki göllerin/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /sözlük|veri kaynakları|doğrulama/i })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 800 });
  const w = await page.evaluate(() => { const h = document.querySelector("header.top")!; return [h.scrollWidth, h.clientWidth]; });
  expect(w[0]).toBeLessThanOrEqual(w[1]);
  await page.reload();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "İçeriğe geç" })).toBeFocused();
});

test("panel shows no method-limitation note even when the API sends mndwi_note", async ({ page }) => {
  await page.route(/\/api\/lakes\/[^/?]+$/, async (r) => {
    const res = await r.fetch(); const j = await res.json();
    j.summary.why_selected = j.summary.why_selected ?? "why text"; j.summary.cadence_note = j.summary.cadence_note ?? "every year";
    j.summary.mndwi_note = "MNDWI limitation: SECRET-NOTE salt crust";
    await r.fulfill({ response: res, json: j });
  });
  await openMap(page);
  await page.evaluate(() => (window as any).__map.jumpTo({ center: [30.17, 37.75], zoom: 6 }));
  await page.waitForTimeout(500);
  const p = await px(page, 30.17, 37.75);
  await page.mouse.click(p.x, p.y);
  await expect(page.getByTestId("panel")).toBeVisible({ timeout: 3000 });
  await expect(page.getByTestId("refinfo")).toBeVisible();
  await expect(page.getByTestId("panel")).not.toContainText(/SECRET-NOTE|Method limitation|Yöntem sınırlaması/);
});

const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

test("legend: size key drawn from circleRadius, darker grey swatch, honest size rule (EN and TR)", async ({ page }) => {
  await openMap(page);
  const key = page.getByTestId("size-key");
  await expect(key).toContainText("Circle area is proportional to lake area");
  await expect(key).toContainText("300 km²"); await expect(key).toContainText("3,000 km²");
  const rs = await key.locator("figure").evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-r"))));
  expect(rs.length).toBe(3);
  // 10x lake area -> sqrt(10) x radius (all three samples sit inside the proportional range)
  expect(rs[2] / rs[1]).toBeCloseTo(Math.sqrt(3), 5);
  const circleR = await key.locator("svg circle").evaluateAll((els) => els.map((e) => Number(e.getAttribute("r"))));
  expect(circleR).toEqual(rs);
  expect(await page.locator(".legend i.ns").evaluate((e) => getComputedStyle(e).backgroundColor)).toBe("rgb(74, 74, 74)");
  const feats = await page.evaluate(() => (window as any).__map.querySourceFeatures("lakes").map((f: any) => f.properties.r));
  expect(Math.max(...feats)).toBeLessThanOrEqual(24); expect(Math.min(...feats)).toBeGreaterThanOrEqual(6);
  await page.getByRole("button", { name: /Switch language/ }).click();
  await expect(page.getByTestId("size-key")).toContainText("Daire alanı göl alanıyla");
});

test("basemap selector has Vector (light) next to Vector (dark); the light style is requested", async ({ page }) => {
  const urls: string[] = [];
  await page.route(/openfreemap|gibs\.earthdata/, (r) => { urls.push(r.request().url()); r.abort(); });
  await page.goto("/");
  const sel = page.getByTestId("toolbar").locator("select");
  await expect(sel.locator("option")).toHaveCount(5);
  const labels = await sel.locator("option").allTextContents();
  expect(labels.slice(0, 2)).toEqual(["Vector (dark)", "Vector (light)"]);
  await sel.selectOption("vectorlight");
  await expect.poll(() => urls.some((u) => u.includes("/styles/positron"))).toBe(true);
});

test("VIIRS date input: min = first daily image, typed earlier/later dates are clamped", async ({ page }) => {
  await page.route(/openfreemap/, (r) => r.abort());
  await page.route(/gibs\.earthdata/, (r) => r.fulfill({ body: PNG, contentType: "image/png" }));
  await page.goto("/");
  await page.getByTestId("toolbar").locator("select").selectOption("viirs");
  const d = page.getByTestId("viirs-date");
  await expect(d).toHaveAttribute("min", "2018-01-05");
  await d.fill("2010-03-01"); await d.blur();
  await expect(d).toHaveValue("2018-01-05");
  await d.fill("2999-03-01"); await d.blur();
  expect(await d.inputValue() <= new Date().toISOString().slice(0, 10)).toBe(true);
  await d.fill("2022-05-06"); await d.blur();
  await expect(d).toHaveValue("2022-05-06");
});
