// Palette: UI chrome uses the owner's swatches (royal blue #0a3c91, red-orange #fc3d23, magenta #ba1e68 on near-black #0e0e0e; see styles.css).
// DATA colours are separate and colour-blind friendly (Okabe-Ito based), chosen to read on near-black AND on the bright Blue Marble basemap.
// Meaning is also given by labels, never by colour alone. Water = cyan, temperature = orange (E69F00, different hue AND lightness from water),
// loss = Okabe-Ito vermillion #D55E00 (hue 27, darker) - deliberately NOT the CTA red-orange #fc3d23 (hue 7); emergence = reddish purple.
// Magenta is UI-only (tags, Turkey marker ring); red-orange / royal blue are UI-only.
export const C = {
  water: "#4cc9e0", waterPale: "#a9e3f2", waterDark: "#0b5f8a",
  temp: "#E69F00", climate: "#a8a8a8", loss: "#D55E00", gain: "#56B4E9", neutral: "#b0b0b0",
  emergence: "#CC79A7", turkey: "#f472ae", text: "#ffffff", muted: "#b0b0b0", grid: "#333333", bg: "#0e0e0e", panel: "#161616", ink: "#0e0e0e",
};
/** Trend classes shared by the map markers, the legend and the compare table: fast = saturated vermillion, slow = pale peach (lightness differs). */
export const TREND = { fast: "#D55E00", slow: "#f7c9a0", ns: "#b0b0b0", inc: "#56B4E9" };
export const LST5 = "#f5c04a"; // Landsat 5 temperature trend line
export const LAKE_COLOURS = ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#CC79A7", "#D55E00"];
/** Map overlay colours: 1985 extent (lost area) pale cream, selected-year water bright cyan; both read on dark and on Blue Marble. */
export const MASK = { base: [255, 244, 214] as [number, number, number], cur: [0, 190, 230] as [number, number, number] };
