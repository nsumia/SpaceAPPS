import { GLOSSARY, useI18n } from "../i18n";

const SOURCES: [string, string, string][] = [
  ["Landsat Collection 2 Level-2 (5, 7, 8, 9) via Microsoft Planetary Computer", "Crawford et al. 2023, Remote Sensing of Environment", "10.1016/j.rse.2023.113776"],
  ["MNDWI water index", "Xu 2006, Int. J. Remote Sensing", "10.1080/01431160600589179"],
  ["Mann-Kendall trend test", "Mann 1945, Econometrica", "10.2307/1907187"],
  ["Sen's slope", "Sen 1968, J. American Statistical Association", "10.1080/01621459.1968.10480934"],
  ["NASA POWER (precipitation, MERRA-2 based)", "Sparks 2018, J. Open Source Software", "10.21105/joss.01035"],
  ["MERRA-2 reanalysis (P-E, EVLAND)", "Gelaro et al. 2017, J. Climate", "10.1175/JCLI-D-16-0758.1"],
  ["HydroBASINS (catchments)", "Lehner and Grill 2013, Hydrological Processes", "10.1002/hyp.9740"],
  ["SWOT L2_HR_LakeSP via Hydrocron (level)", "PO.DAAC, NASA/CNES; no lake id configured yet, so levels are not available", ""],
  ["NASA GIBS (basemaps), OpenFreeMap / OpenStreetMap, Natural Earth lakes", "see each provider's terms; attribution is shown on the map", ""],
];

export default function MethodsPage() {
  const { t, lang } = useI18n();
  return (
    <div className="page prose">
      <h1>{t("methods.title")}</h1>
      <h2>{t("how.title")}</h2>
      <p>{t("how.body")}</p>
      <h2 id="glossary">{t("gl.title")}</h2>
      <p className="muted">{t("gl.intro")}</p>
      <dl className="glossary" data-testid="glossary">
        {GLOSSARY.map(([term, en, tr]) => (<div key={term}><dt>{term}</dt><dd>{lang === "tr" ? tr : en}</dd></div>))}
      </dl>
      <h2>Data sources</h2>
      <table>
        <thead><tr><th>Data / method</th><th>Reference</th><th>DOI</th></tr></thead>
        <tbody>{SOURCES.map(([a, b, doi]) => (
          <tr key={a}><td>{a}</td><td>{b}</td><td>{doi ? <a href={`https://doi.org/${doi}`} target="_blank" rel="noreferrer">{doi}</a> : "-"}</td></tr>))}</tbody>
      </table>
      <h2>Method</h2>
      <ul>
        <li>Lake area: MNDWI water mask on the Aug-Sep median of all Landsat scenes (cloud cover under 40 %) per year, 1985 to the last complete year; 30 m pixels for lakes under about 1000 km2, 60 or 120 m for large lakes. Pixels without valid data are excluded and reported as valid fraction.</li>
        <li>Trend: Mann-Kendall test and Sen's slope on the yearly area. The summary sentence compares the 1985-1990 mean with the mean of the last three valid years (not a single start year). Reference lakes with a coarser cadence (every 2nd/3rd year) are shown with their cadence and resolution; unobserved years are not interpolated.</li>
        <li>Natural-variability band (grey area in the area chart): mean of the reference period (the first 12 years of the record) plus/minus 2 sigma, where sigma is the standard deviation of the detrended reference values. It is not a confidence interval of the data.</li>
        <li>Emergence year: the first year after which the Sen line stays outside the reference mean +/- 2 sigma. When the line was already outside at the end of the reference period, the year is shown as "by &lt;year&gt;" (left-censored): the real date is earlier or equal.</li>
        <li>Surface temperature: Landsat thermal band, Aug-Sep. Warming uses Landsat 5 only (1985-2012), because Landsat 5 to 8 shows a step of about +3 C at 2012/13.</li>
        <li>Climate or human: yearly area change is regressed on precipitation minus evaporation (water-year, NASA POWER / MERRA-2) over the 1985-1999 reference; the model is extrapolated after 1999 and the observed minus predicted cumulative loss is the unexplained part. Bootstrap confidence intervals are shown; when the reference skill is weak or the share is outside 0-1, the share is declared not computable.</li>
        <li>Forecast to 2040: three simple models are fitted to the valid yearly areas (Sen trend of the whole record, Sen trend of the last 15 valid years, and "stays at the mean of the last 3 valid years"). Each is tested on the past: it is fitted to the years up to a cut-off and scored on the following 10 years, for every possible cut-off. The model with the smallest error is used, and a trend model only if it beats "no change" by more than 5 %. The bands come from 2000 simulated futures (trend refitted on resampled years, plus year-to-year noise with memory) and show the 25-75 % and 5-95 % ranges. No forecast is made for low-reliability lakes or lakes with fewer than 15 valid years; numbers are not printed when the 90 % band held under 70 % of the real values in the test.</li>
        <li>On-demand analyses use the same pipeline but are labelled unverified.</li>
      </ul>
      <h2>Validation</h2>
      <ul>
        <li>Burdur: our areas compared with Sabuncu 2020 (doi 10.35414/akufemubid.711653): 206 km2 (1986) and 125 km2 (2019); ours is an Aug-Sep composite, so it is somewhat lower in the dry season. This is the only lake labelled "validated".</li>
        <li>Van, Akşehir, Eğirdir: checked for plausibility only (unverified).</li>
        <li>The full validation notes are in <code>VALIDATION.md</code> in the repository.</li>
      </ul>
      <h2>Limitations</h2>
      <ul>
        <li>Akşehir is flagged low reliability: shallow, ephemeral water makes single years jump; its trend, emergence year and climate share are not reliable.</li>
        <li>The climate share is only a statistical attribution. Burdur and Van have weak reference skill, so it is reported as not computable. The unexplained part is a sign, not proof, of human impact.</li>
        <li>MERRA-2 is model output on a coarse grid (about 0.5 x 0.625 degrees); EVLAND is a land-surface proxy, not open-water evaporation.</li>
        <li>Resolution differs between lakes (30 m vs 60/120 m), so compare trends rather than single-year values.</li>
        <li>SWOT levels are not available for lakes without a configured prior-lake id; the volume chart then shows "no data".</li>
        <li>The forecast only continues the past pattern of the area series. It does not use future rainfall, temperature, water policy, dams or pumping, it is not a climate projection, and a sudden change (a new dam, a wet decade, a diversion) will break it.</li>
        <li>MNDWI can be wrong in very shallow or vegetated water and with salt crusts.</li>
        <li>Live cards come from public APIs and can be cached (up to 3 h) or stale; the label says so.</li>
      </ul>
    </div>
  );
}
