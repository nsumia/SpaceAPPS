import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "en" | "tr";
export type TFn = (key: string, vars?: Record<string, string | number>) => string;

const en: Record<string, string> = {
  "app.title": "Lake Loss Detective", "nav.map": "Map", "nav.compare": "Compare", "nav.methods": "Methods",
  "map.basemap": "Basemap", "bm.vector": "Vector (dark)", "bm.blue": "NASA Blue Marble", "bm.viirs": "NASA VIIRS daily", "bm.none": "Offline (plain)",
  "map.date": "Date", "map.draw": "Draw area", "map.rect": "Rectangle", "map.poly": "Polygon", "map.clear": "Clear",
  "map.legend": "Trend", "leg.fast": "fast loss", "leg.slow": "loss", "leg.ns": "not significant", "leg.inc": "increase", "leg.size": "marker size = lake area",
  "map.loading": "Loading lakes...", "map.hint": "Click a lake or draw an area to analyse.",
  "panel.close": "Close", "panel.add": "Add to compare", "panel.remove": "Remove from compare", "panel.compare": "Open compare",
  "badge.validated": "validated", "badge.unverified": "unverified", "badge.rel.ok": "reliability: ok", "badge.rel.low": "reliability: LOW", "badge.rel.unknown": "reliability: unknown",
  "live.title": "Live now", "live.area": "Water area", "live.lst": "Surface temperature", "live.swot": "SWOT water level", "live.precip": "Water-year precipitation",
  "live.loading": "Fetching live data (the first call can take about 30 s)...", "live.cache": "cache", "live.stale": "stale", "live.data": "data", "live.source": "source",
  "live.unavailable": "unavailable", "live.vsly": "vs same window last year", "live.ofnormal": "of 1991-2020 normal", "live.nodata": "no data",
  "chart.area": "Lake area", "chart.lst": "Land/lake surface temperature (Aug-Sep)", "chart.climate": "Climate or human? Cumulative loss since 1999", "chart.volume": "Volume change (SWOT area-level curve)",
  "chart.source.landsat": "Source: Landsat C2 L2 via Planetary Computer, Aug-Sep median composite",
  "chart.source.climate": "Source: NASA POWER / MERRA-2 (P-E) + Landsat area; model output, not stations",
  "chart.source.swot": "Source: SWOT L2_HR_LakeSP area-level fit + Landsat area",
  "ax.year": "Year", "ax.area": "Area (km2)", "ax.temp": "Temperature (C)", "ax.loss": "Cumulative loss (km2)", "ax.dv": "Volume change (km3)",
  "ser.observed": "observed", "ser.sen": "Sen trend", "ser.band": "natural-variability band (reference mean ± 2σ, first 12 years)", "ser.predicted": "climate-predicted", "ser.gap": "gap (unexplained)", "ser.lst": "LST", "ser.lst5": "Sen trend, Landsat 5 only",
  "em.by": "emerged by {year}", "em.at": "emerged {year}", "lst.break": "Sensor break: Landsat 5 to 8 (+3 C step around 2012/13)",
  "climate.na": "Not computable", "climate.reason": "Reason", "climate.show": "show the (non-interpretable) curves anyway",
  "climate.note": "The unexplained part is a sign, not proof, of human impact (irrigation, withdrawals, model error and land-use change all end up in it).",
  "volume.none": "No data", "volume.extrap": "outside the SWOT-observed range (extrapolated)",
  "sum.title": "Summary (generated from a template, not by AI)",
  "sum.lost": "{name}: the mean area of its last 3 valid years ({y0}-{y1}) is {pct}% below its {r0}-{r1} average ({sig}).", "sum.gained": "{name}: the mean area of its last 3 valid years ({y0}-{y1}) is {pct}% above its {r0}-{r1} average ({sig}).",
  "sum.significant": "significant, {p}", "sum.notsignificant": "not significant, {p}",
  "sum.emerged": "The change separated from natural variability in {year}.", "sum.emerged_by": "The change had already separated from natural variability by {year} (the true year is earlier or equal).",
  "sum.climate": "Climate variables explain about {share}% of the loss (90% CI {lo}-{hi}%).", "sum.climate_na": "The climate share is not computable for this lake.", "sum.nodata": "{name}: not enough data for a summary.",
  "an.analyze": "Analyze this lake", "an.analyze_area": "Analyze the largest water body in the drawn area", "an.progress": "Analysis running", "an.year": "year", "an.eta": "ETA", "an.phase": "phase",
  "an.prelim": "Preliminary result (every 5th year first); charts fill in as years arrive.", "an.failed": "Analysis failed", "an.done": "Analysis finished",
  "an.unverified": "On-demand analysis: unverified, not validated against literature.", "an.error": "Cannot analyze",
  "timeline.year": "Year", "timeline.play": "Play", "timeline.pause": "Pause", "timeline.legend": "1985 mask pale blue, selected year dark blue",
  "cmp.title": "Compare lakes", "cmp.empty": "Add up to 6 lakes from the list below or from the map.", "cmp.chart": "Normalised lake area (1985-1990 mean = 100%)",
  "cmp.table": "Ranking", "cmp.scatter": "Where do Turkish lakes sit? Warming vs area trend", "cmp.add": "Add", "cmp.remove": "Remove", "cmp.max": "Maximum 6 lakes",
  "col.name": "Lake", "col.trend": "Area trend (%/decade)", "col.p": "p", "col.emergence": "Emergence", "col.warming": "Warming (C/decade)", "col.climate": "Climate share",
  "cmp.res": "Resolution differs between lakes (30 m for small lakes, 60/120 m for large ones); compare trends, not single-year values.",
  "cmp.x": "Warming, Landsat 5 only (C/decade)", "cmp.y": "Area trend (%/decade)", "cmp.size": "bubble size = latest lake area", "cmp.colour": "colour = climate share", "cmp.nocl": "no climate share",
  "cmp.turkey": "Turkish lake", "cmp.reference": "Reference lake", "cmp.na": "n/a", "grp.all": "All", "grp.turkey": "Turkish", "grp.reference": "Reference", "col.group": "Group",
  "ref.why": "Why selected", "ref.mndwi": "Method limitation", "ref.cadence": "Cadence and resolution", "ref.lit": "Literature direction", "ref.agree": "agrees with our trend", "ref.conflict": "conflicts with our trend (see VALIDATION.md)", "ref.mixed": "no single direction in the literature, so no agreement test", "leg.turkey": "gold ring = Turkish lake, dark ring = reference lake",
  "methods.title": "Methods and limitations",
  "err.generic": "Something went wrong", "retry": "Retry",
};
const tr: Record<string, string> = {
  "app.title": "Göl Kaybı Dedektifi", "nav.map": "Harita", "nav.compare": "Karşılaştır", "nav.methods": "Yöntem",
  "map.basemap": "Altlık", "bm.vector": "Vektör (koyu)", "bm.blue": "NASA Blue Marble", "bm.viirs": "NASA VIIRS günlük", "bm.none": "Çevrimdışı (düz)",
  "map.date": "Tarih", "map.draw": "Alan çiz", "map.rect": "Dikdörtgen", "map.poly": "Poligon", "map.clear": "Temizle",
  "map.legend": "Eğilim", "leg.fast": "hızlı kayıp", "leg.slow": "kayıp", "leg.ns": "anlamsız", "leg.inc": "artış", "leg.size": "işaret boyutu = göl alanı",
  "map.loading": "Göller yükleniyor...", "map.hint": "Bir göle tıklayın ya da analiz için alan çizin.",
  "panel.close": "Kapat", "panel.add": "Karşılaştırmaya ekle", "panel.remove": "Karşılaştırmadan çıkar", "panel.compare": "Karşılaştırmayı aç",
  "badge.validated": "doğrulanmış", "badge.unverified": "doğrulanmamış", "badge.rel.ok": "güvenilirlik: iyi", "badge.rel.low": "güvenilirlik: DÜŞÜK", "badge.rel.unknown": "güvenilirlik: bilinmiyor",
  "live.title": "Şu an (canlı)", "live.area": "Su alanı", "live.lst": "Yüzey sıcaklığı", "live.swot": "SWOT su seviyesi", "live.precip": "Su yılı yağışı",
  "live.loading": "Canlı veri alınıyor (ilk çağrı yaklaşık 30 sn sürebilir)...", "live.cache": "önbellek", "live.stale": "eski", "live.data": "veri", "live.source": "kaynak",
  "live.unavailable": "alınamadı", "live.vsly": "geçen yılın aynı dönemine göre", "live.ofnormal": "1991-2020 normalinin", "live.nodata": "veri yok",
  "chart.area": "Göl alanı", "chart.lst": "Yüzey sıcaklığı (Ağu-Eyl)", "chart.climate": "İklim mi, insan mı? 1999'dan beri kümülatif kayıp", "chart.volume": "Hacim değişimi (SWOT alan-seviye eğrisi)",
  "chart.source.landsat": "Kaynak: Landsat C2 L2 (Planetary Computer), Ağu-Eyl medyan kompozit",
  "chart.source.climate": "Kaynak: NASA POWER / MERRA-2 (P-E) + Landsat alanı; model çıktısı, istasyon değil",
  "chart.source.swot": "Kaynak: SWOT L2_HR_LakeSP alan-seviye uyumu + Landsat alanı",
  "ax.year": "Yıl", "ax.area": "Alan (km2)", "ax.temp": "Sıcaklık (C)", "ax.loss": "Kümülatif kayıp (km2)", "ax.dv": "Hacim değişimi (km3)",
  "ser.observed": "gözlenen", "ser.sen": "Sen eğilimi", "ser.band": "doğal değişkenlik bandı (referans ort. ± 2σ, ilk 12 yıl)", "ser.predicted": "iklimden tahmin", "ser.gap": "fark (açıklanamayan)", "ser.lst": "LST", "ser.lst5": "Sen eğilimi, yalnız Landsat 5",
  "em.by": "{year} yılına kadar ayrıştı", "em.at": "{year} yılında ayrıştı", "lst.break": "Sensör kırılması: Landsat 5'ten 8'e (2012/13 civarı +3 C basamak)",
  "climate.na": "Hesaplanamıyor", "climate.reason": "Neden", "climate.show": "yine de (yorumlanamaz) eğrileri göster",
  "climate.note": "Açıklanamayan kısım insan etkisinin kanıtı değil, işaretidir (sulama, çekim, model hatası ve arazi kullanımı değişimi hep buraya düşer).",
  "volume.none": "Veri yok", "volume.extrap": "SWOT gözlem aralığı dışında (tahmin)",
  "sum.title": "Özet (şablonla üretildi, yapay zekâ değil)",
  "sum.lost": "{name}: son 3 geçerli yılın ({y0}-{y1}) ortalama alanı, {r0}-{r1} ortalamasının %{pct} altında ({sig}).", "sum.gained": "{name}: son 3 geçerli yılın ({y0}-{y1}) ortalama alanı, {r0}-{r1} ortalamasının %{pct} üstünde ({sig}).",
  "sum.significant": "anlamlı, {p}", "sum.notsignificant": "anlamsız, {p}",
  "sum.emerged": "Değişim {year} yılında doğal dalgalanmadan ayrıştı.", "sum.emerged_by": "Değişim {year} yılına kadar doğal dalgalanmadan ayrışmıştı (gerçek yıl daha erken ya da aynı).",
  "sum.climate": "İklim değişkenleri kaybın yaklaşık %{share}'ini açıklıyor (%90 GA %{lo}-{hi}).", "sum.climate_na": "Bu göl için iklim payı hesaplanamıyor.", "sum.nodata": "{name}: özet için yeterli veri yok.",
  "an.analyze": "Bu gölü analiz et", "an.analyze_area": "Çizilen alandaki en büyük su kütlesini analiz et", "an.progress": "Analiz sürüyor", "an.year": "yıl", "an.eta": "Tahmini süre", "an.phase": "aşama",
  "an.prelim": "Ön sonuç (önce her 5. yıl); yıllar geldikçe grafikler dolar.", "an.failed": "Analiz başarısız", "an.done": "Analiz tamamlandı",
  "an.unverified": "İsteğe bağlı analiz: doğrulanmamış, literatürle karşılaştırılmadı.", "an.error": "Analiz edilemiyor",
  "timeline.year": "Yıl", "timeline.play": "Oynat", "timeline.pause": "Duraklat", "timeline.legend": "1985 maskesi soluk mavi, seçili yıl koyu mavi",
  "cmp.title": "Gölleri karşılaştır", "cmp.empty": "Aşağıdaki listeden ya da haritadan en fazla 6 göl ekleyin.", "cmp.chart": "Normalleştirilmiş göl alanı (1985-1990 ort. = %100)",
  "cmp.table": "Sıralama", "cmp.scatter": "Türkiye gölleri nerede? Isınma ve alan trendi", "cmp.add": "Ekle", "cmp.remove": "Çıkar", "cmp.max": "En fazla 6 göl",
  "col.name": "Göl", "col.trend": "Alan trendi (%/on yıl)", "col.p": "p", "col.emergence": "Ayrışma", "col.warming": "Isınma (C/on yıl)", "col.climate": "İklim payı",
  "cmp.res": "Çözünürlük göller arasında farklıdır (küçüklerde 30 m, büyüklerde 60/120 m); tek yıl değerlerini değil trendleri karşılaştırın.",
  "cmp.x": "Isınma, yalnız Landsat 5 (C/on yıl)", "cmp.y": "Alan trendi (%/on yıl)", "cmp.size": "balon boyutu = son göl alanı", "cmp.colour": "renk = iklim payı", "cmp.nocl": "iklim payı yok",
  "cmp.turkey": "Türkiye gölü", "cmp.reference": "Referans göl", "cmp.na": "yok", "grp.all": "Hepsi", "grp.turkey": "Türkiye", "grp.reference": "Referans", "col.group": "Grup",
  "ref.why": "Neden seçildi", "ref.mndwi": "Yöntem sınırlaması", "ref.cadence": "Örnekleme sıklığı ve çözünürlük", "ref.lit": "Literatürdeki yön", "ref.agree": "bizim eğilimle uyumlu", "ref.conflict": "bizim eğilimle çelişiyor (bkz. VALIDATION.md)", "ref.mixed": "literatürde tek bir yön yok, uyum testi yapılmadı", "leg.turkey": "altın halka = Türkiye gölü, koyu halka = referans göl",
  "methods.title": "Yöntem ve sınırlamalar",
  "err.generic": "Bir sorun oluştu", "retry": "Tekrar dene",
};
const dict = { en, tr };

export function makeT(lang: Lang): TFn {
  return (key, vars) => {
    let s = dict[lang][key] ?? en[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    return s;
  };
}

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: TFn }>({ lang: "en", setLang: () => {}, t: makeT("en") });
export const useI18n = () => useContext(Ctx);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setL] = useState<Lang>(initial ?? ((localStorage.getItem("lang") as Lang) || "en"));
  const setLang = (l: Lang) => { localStorage.setItem("lang", l); document.documentElement.lang = l; setL(l); };
  return <Ctx.Provider value={{ lang, setLang, t: makeT(lang) }}>{children}</Ctx.Provider>;
}
