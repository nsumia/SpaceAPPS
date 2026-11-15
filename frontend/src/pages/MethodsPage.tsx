import { GLOSSARY, useI18n } from "../i18n";

const GIBS = "https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api";

// Product names stay in English; descriptions come from i18n (src.<n>). One continuous 1-10 numbering.
type Group = "nasa" | "partner" | "other";
export const SOURCES: { n: number; group: Group; name: string; url: string }[] = [
  { n: 1, group: "nasa", name: "NASA POWER monthly API", url: "https://power.larc.nasa.gov/" },
  { n: 2, group: "nasa", name: "MERRA-2 tavg1_2d_lnd_Nx (NASA GMAO)", url: "https://www.earthdata.nasa.gov/data/catalog/ges-disc-m2t1nxlnd-5.12.4" },
  { n: 3, group: "nasa", name: "NASA GIBS, layer VIIRS NOAA-20 Corrected Reflectance True Color", url: GIBS },
  { n: 4, group: "nasa", name: "NASA GIBS, layer Blue Marble Shaded Relief and Bathymetry", url: GIBS },
  { n: 5, group: "partner", name: "Landsat 4-5 TM Collection 2 Level-2 (NASA/USGS)", url: "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-landsat-archives-landsat-4-5-tm-collection-2-level-2-science" },
  { n: 6, group: "partner", name: "Landsat 8-9 OLI/TIRS Collection 2 Level-2 (NASA/USGS)", url: "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-landsat-archives-landsat-8-9-olitirs-collection-2-level-2" },
  { n: 7, group: "other", name: "Microsoft Planetary Computer", url: "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2" },
  { n: 8, group: "other", name: "HydroBASINS (HydroSHEDS)", url: "https://www.hydrosheds.org/products/hydrobasins" },
  { n: 9, group: "other", name: "Natural Earth 10m lakes and countries", url: "https://www.naturalearthdata.com/downloads/10m-physical-vectors/" },
  { n: 10, group: "other", name: "OpenFreeMap", url: "https://openfreemap.org/" },
];

export default function MethodsPage() {
  const { t, lang } = useI18n();
  const list = (group: Group) => {
    const items = SOURCES.filter((s) => s.group === group);
    return (
      <>
        <h3>{t(`src.${group}`)}</h3>
        <ol className="sources" start={SOURCES.indexOf(items[0]) + 1}>
          {items.map((s) => (
            <li key={s.n}>
              <a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a>
              {" - "}{t(`src.${s.n}`)}
            </li>
          ))}
        </ol>
      </>
    );
  };
  return (
    <div className="page prose">
      <h1>{t("methods.title")}</h1>
      <h2>{t("sum.proj.title")}</h2>
      <p>{t("sum.proj.body")}</p>
      <h2>{t("how.title")}</h2>
      <p>{t("how.body")}</p>
      <h2 id="glossary">{t("gl.title")}</h2>
      <p className="muted">{t("gl.intro")}</p>
      <dl className="glossary" data-testid="glossary">
        {GLOSSARY.map(([term, en, tr]) => (<div key={term}><dt>{term}</dt><dd>{lang === "tr" ? tr : en}</dd></div>))}
      </dl>
      <h2>{t("src.title")}</h2>
      {list("nasa")}
      {list("partner")}
      {list("other")}
    </div>
  );
}
