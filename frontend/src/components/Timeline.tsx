import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { api } from "../lib/api";

export default function Timeline({ lakeId, years, year, setYear }: { lakeId: string; years: [number, number]; year: number; setYear: (y: number) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [playing, setPlaying] = useState(false);
  const yr = useRef(year);
  yr.current = year;
  useEffect(() => {
    if (!playing) return;
    let stop = false;
    (async () => {
      while (!stop) {
        const next = yr.current >= years[1] ? years[0] : yr.current + 1;
        try { await qc.fetchQuery({ queryKey: ["mask", lakeId, next], queryFn: () => api.mask(lakeId, next), staleTime: Infinity }); } catch { /* missing year */ }
        if (stop) return;
        setYear(next);
        await new Promise((r) => setTimeout(r, 450));
      }
    })();
    return () => { stop = true; };
  }, [playing, lakeId]);
  return (
    <div className="timeline" data-testid="timeline">
      <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? t("timeline.pause") : t("timeline.play")}>{playing ? "❚❚" : "▶"}</button>
      <input type="range" min={years[0]} max={years[1]} value={year} onChange={(e) => setYear(+e.target.value)} aria-label={t("timeline.year")} />
      <strong>{year}</strong>
      <span className="small muted">{t("timeline.legend")}</span>
    </div>
  );
}
