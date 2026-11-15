// Palette sampled from the owner's photo (slate-teal #1c3136, deep teal #074554, mustard #a87615, ochre #88551c, near-black #242520).
// UI chrome uses those hues (see styles.css). DATA colours are separate and colour-blind friendly (Okabe-Ito based), chosen to read
// on near-black/slate AND on the bright Blue Marble basemap. Meaning is also given by labels, never by colour alone.
// Water = cyan/blue family, temperature = orange (different hue AND lightness from water), loss = vermillion, climate/reference = warm grey,
// emergence = reddish purple. Mustard/ochre are UI-only highlights, not data classes.
export const C = {
  water: "#4cc9e0", waterPale: "#a9e3f2", waterDark: "#0b5f8a",
  temp: "#E69F00", climate: "#a8a595", loss: "#ff6b57", gain: "#56B4E9", neutral: "#a9b0a6",
  emergence: "#e08fbf", sand: "#e3ac3c", ochre: "#cf9455", text: "#f2ead9", muted: "#aeb5ac", grid: "#2f4a50", bg: "#171915", panel: "#202220", ink: "#14110a",
};
/** Trend classes shared by the map markers, the legend and the compare table: fast = saturated vermillion, slow = pale salmon (lightness differs). */
export const TREND = { fast: "#ff5a45", slow: "#f7b9a6", ns: "#a9b0a6", inc: "#56B4E9" };
export const LST5 = "#f5c04a"; // Landsat 5 temperature trend line
export const LAKE_COLOURS = ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#CC79A7", "#D55E00"];
/** Map overlay colours: 1985 extent (lost area) pale cream, selected-year water bright cyan; both read on dark and on Blue Marble. */
export const MASK = { base: [242, 234, 217] as [number, number, number], cur: [0, 190, 230] as [number, number, number] };
