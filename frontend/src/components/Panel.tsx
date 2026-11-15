import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { api, ApiError, useCompareIds, useLake, useLakes, useLive, type Job, type LakeFull, type Live, type LiveCard } from "../lib/api";
import { summarySentence } from "../lib/util";
import { AreaChart, ClimateChart, ForecastChart, LstChart } from "./Charts";
import { Link } from "react-router-dom";

export interface Selection { id: string | null; name?: string; polygon?: GeoJSON.Geometry | null }

/** Headline numbers, straight from the summary record. */
export function Stats({ s }: { s: LakeFull["summary"] }) {
  const { t } = useI18n();
  const signed = (x: number, d = 0) => (x > 0 ? "+" : x < 0 ? "\u2212" : "") + Math.abs(x).toFixed(d);
  const rf = s.ref_years ?? [1985, 1990], change = s.total_loss_pct == null ? null : -s.total_loss_pct, tr = s.trend_pct_per_decade;
  const cls = (x: number | null | undefined) => (x == null || x === 0 ? "" : x < 0 ? "down" : "up");
  const na = <span className="muted">{"\u2013"}</span>;
  return (
    <dl className="stats" data-testid="stats">
      <div><dt>{t("stat.now", { year: s.latest_area_year ?? "" })}</dt><dd>{s.latest_area_km2 == null ? na : <>{s.latest_area_km2.toFixed(0)} <small>km²</small></>}</dd></div>
      <div><dt>{t("stat.change", { r0: rf[0], r1: rf[1] })}</dt><dd className={cls(change)}>{change == null ? na : <>{signed(change)} <small>%</small></>}</dd></div>
      <div><dt>{t("stat.trend")}</dt><dd className={s.trend_p != null && s.trend_p < 0.05 ? cls(tr) : ""}>{tr == null ? na : <>{signed(tr, 1)} <small>%{s.trend_p != null && s.trend_p >= 0.05 ? ` (${t("sig.no.long")})` : ""}</small></>}</dd></div>
      <div><dt>{t("stat.fc", { year: s.forecast_year ?? 2040 })}</dt><dd>{s.forecast_km2 == null ? na : <>{s.forecast_km2.toFixed(0)} <small>km²</small></>}</dd></div>
    </dl>
  );
}

export function RefInfo({ s }: { s: LakeFull["summary"] }) {
  const { t } = useI18n();
  if (!s.why_selected && !s.cadence_note) return null;
  const lit = s.literature_direction;
  return (
    <section className="refinfo" data-testid="refinfo">
      {s.why_selected && <p><strong>{t("ref.why")}:</strong> {s.why_selected}</p>}
      <p className="small"><strong>{t("ref.cadence")}:</strong> {s.cadence_note ?? "?"}; {s.resolution_m ?? "?"} m{s.window ? `; ${s.window[0]} to ${s.window[1]}` : ""}</p>
      {lit && <p className="small"><strong>{t("ref.lit")}:</strong> {lit} ({t(`ref.a.${s.literature_agreement ?? "not_tested"}`)})</p>}
    </section>
  );
}

export function eta(progress: number, startedMs: number, nowMs: number): string | null {
  if (progress < 6) return null;
  const el = (nowMs - startedMs) / 1000, rem = (el * (100 - progress)) / progress;
  return rem < 90 ? `${Math.round(rem)} s` : `${Math.round(rem / 60)} min`;
}

export function AnalysisProgress({ job, started }: { job: Job; started: number }) {
  const { t } = useI18n();
  const e = eta(job.progress, started, Date.now());
  return (
    <div className="progress" role="status" data-testid="analysis-progress">
      <div><strong>{t("an.progress")}</strong> {job.status === "queued" ? "(queued)" : ""}</div>
      <div className="bar" role="progressbar" aria-valuenow={Math.round(job.progress)} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: `${Math.max(2, job.progress)}%` }} />
      </div>
      <div className="small">{Math.round(job.progress)}% | {t("an.year")}: {job.current_year ?? "-"} | {t("an.phase")}: {job.phase ?? "-"} | {t("an.eta")}: {e ?? "..."}</div>
    </div>
  );
}

const num = (x: unknown, d = 1) => (typeof x === "number" ? x.toFixed(d) : "-");

function Card({ title, card, children, date }: { title: string; card?: LiveCard; children?: React.ReactNode; date?: string }) {
  const { t } = useI18n();
  const ok = card?.ok;
  return (
    <div className="card" data-testid="live-card">
      <div className="card-h">
        <span>{title}</span>
      </div>
      {ok ? <div className="card-v">{children}</div> : <div className="card-v muted">{t("live.nodata")}{card?.error ? <div className="small">{card.error}</div> : null}</div>}
      <div className="src small">
        {t("live.source")}: {card?.source ?? "-"}{date ? <> | {t("live.data")}: {date}</> : null}
      </div>
    </div>
  );
}

function Snapshot({ card }: { card?: LiveCard }) {
  const { t } = useI18n();
  const live = typeof card?.image_url === "string" ? card.image_url : null;
  const snap = typeof card?.snapshot_url === "string" ? card.snapshot_url : null;
  const [src, setSrc] = useState(live ?? snap);
  if (!src) return (
    <div className="card" data-testid="gibs-card-empty">
      <div className="card-h"><span>{t("live.snapshot")}</span></div>
      <div className="card-v muted">{t("live.nocache")}</div>
    </div>
  );
  return (
    <div className="card" data-testid="gibs-card">
      <div className="card-h"><span>{t("live.snapshot")}</span></div>
      <img src={src} alt="VIIRS" onError={() => { if (snap && src !== snap) setSrc(snap); else setSrc(null); }} />
      <div className="src small">{t("live.source")}: {card?.source ?? "NASA GIBS"}</div>
    </div>
  );
}

export function LiveCards({ live, loading, error }: { live?: Live; loading: boolean; error?: Error | null }) {
  const { t } = useI18n();
  if (loading) return <div className="spinner-row" role="status"><span className="spinner" /> {t("live.loading")}</div>;
  if (error || !live) return <div className="note">{t("live.unavailable")}{error ? `: ${error.message}` : ""}</div>;
  const c = live.cards;
  const l = c.landsat, p = c.precip;
  const latest = typeof l?.latest_scene === "string" ? l.latest_scene : undefined;
  return (
    <div className="cards">
      <Card title={t("live.area")} card={l} date={latest}>
        <b>{num(l?.area_km2)}</b> km²
        <div className="small">{t("live.vsly")}: {num(l?.change_vs_last_year_pct)}%</div>
      </Card>
      <Card title={t("live.lst")} card={l} date={latest}>
        <b>{num(l?.lst_c)}</b> °C
        <div className="small">{t("live.vsly")}: {num(l?.lst_change_vs_last_year_c)} °C</div>
      </Card>
      <Card title={t("live.precip")} card={p} date={typeof p?.data_until === "string" ? p.data_until : undefined}>
        <b>{num(p?.precip_mm, 0)}</b> mm
        <div className="small">{String(p?.pct_of_normal ?? "-")}% {t("live.ofnormal")}</div>
      </Card>
      <Snapshot card={c.gibs} />
    </div>
  );
}

export interface PanelLayout { width: number; expanded: boolean }
const MIN_W = 340;
export const clampWidth = (w: number, vw: number) => Math.round(Math.min(Math.max(w, MIN_W), Math.max(MIN_W, vw * 0.85)));

export default function Panel({ sel, onClose, layout, onLayout }: { sel: Selection; onClose: () => void; layout?: PanelLayout; onLayout?: (l: PanelLayout) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const lakes = useLakes();
  const [ids, add, remove] = useCompareIds();
  const [jobId, setJobId] = useState<string | null>(null);
  const [lakeId, setLakeId] = useState<string | null>(sel.id);
  const [err, setErr] = useState<string | null>(null);
  const started = useRef(Date.now());
  useEffect(() => { setLakeId(sel.id); setJobId(null); setErr(null); }, [sel.id, sel.polygon]);

  const known = !!lakeId && !!lakes.data?.some((l) => l.id === lakeId || l.alias === lakeId);
  const job = useQuery({ queryKey: ["job", jobId], queryFn: () => api.job(jobId!), enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["done", "failed"].includes(q.state.data.status) ? false : 2000) });
  const running = !!jobId && job.data?.status !== "done" && job.data?.status !== "failed";
  const lake = useLake(lakeId, running);
  const live = useLive(known && lake.data ? lakeId : null);
  useEffect(() => { if (job.data?.status === "done") { qc.invalidateQueries({ queryKey: ["lakes"] }); qc.invalidateQueries({ queryKey: ["lake", lakeId] }); } }, [job.data?.status]);

  const start = async () => {
    setErr(null);
    try {
      const r = await api.analyze({ lake_id: sel.id! });
      started.current = Date.now();
      setLakeId(r.lake_id ?? lakeId);
      if (r.job_id) setJobId(r.job_id); else qc.invalidateQueries({ queryKey: ["lakes"] });
    } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };

  const d = lake.data;
  const inCompare = !!d && (ids.includes(d.summary.id) || (!!d.summary.alias && ids.includes(d.summary.alias)));
  const isSample = !!d?.analysis?.sample; // a cached sample result still hides unverified/live blocks
  const canAnalyze = !running && (!d || (d.analysis && d.analysis.status === "failed")) && !!sel.id;
  const lay = layout ?? { width: 430, expanded: false };
  const drag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!onLayout) return;
    e.preventDefault();
    const move = (ev: PointerEvent) => onLayout({ width: clampWidth(window.innerWidth - ev.clientX, window.innerWidth), expanded: false });
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const key = (e: React.KeyboardEvent) => {
    if (!onLayout || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
    e.preventDefault();
    onLayout({ width: clampWidth((lay.expanded ? window.innerWidth * 0.7 : lay.width) + (e.key === "ArrowLeft" ? 40 : -40), window.innerWidth), expanded: false });
  };
  return (
    <aside className={"panel" + (lay.expanded ? " expanded" : "")} data-testid="panel" style={{ "--panel-w": lay.expanded ? "min(72vw, 1100px)" : `${lay.width}px` } as React.CSSProperties}>
      <div className="panel-resize" role="separator" aria-orientation="vertical" tabIndex={0} aria-label={t("panel.resize")} title={t("panel.resize")} data-testid="panel-resize" onPointerDown={drag} onKeyDown={key} />
      <div className="panel-top">
        {onLayout && <button className="expand" data-testid="panel-expand" aria-pressed={lay.expanded} onClick={() => onLayout({ ...lay, expanded: !lay.expanded })}
          title={t(lay.expanded ? "panel.collapse" : "panel.expand")} aria-label={t(lay.expanded ? "panel.collapse" : "panel.expand")}>{lay.expanded ? "⇥" : "⇤"}</button>}
        <button className="close" onClick={onClose} aria-label={t("panel.close")}>×</button>
      </div>
      <h2>{d?.summary.name ?? sel.name ?? "…"}</h2>
      {d && d.series.length > 0 && <Stats s={d.summary} />}
      {d && <RefInfo s={d.summary} />}
      {d && (
        <div className="actions">
          <button onClick={() => (inCompare ? remove(d.summary.id, d.summary.alias ?? "") : add(d.summary.id))} disabled={!inCompare && ids.length >= 6}>
            {inCompare ? t("panel.remove") : t("panel.add")}
          </button>
          {ids.length > 0 && <Link to="/compare" className="btn">{t("panel.compare")} ({ids.length})</Link>}
        </div>)}
      {canAnalyze && <button className="primary" onClick={start} data-testid="analyze">{t("an.analyze")}</button>}
      {err && <div className="note bad" role="alert"><strong>{t("an.error")}:</strong> {err}</div>}
      {job.data && running && <AnalysisProgress job={job.data} started={started.current} />}
      {job.data?.status === "failed" && <div className="note bad" role="alert">{t("an.failed")}: {job.data.error}</div>}
      {running && d && <div className="note">{t("an.prelim")}</div>}
      {d?.unverified && !isSample && <div className="note warn">{t("an.unverified")}</div>}
      {d && d.series.length > 0 && (
        <>
          <section><h4>{t("sum.title")}</h4><p className="summary" data-testid="summary">{summarySentence(d.summary, t)}</p></section>
          {known && !isSample && <section><h4>{t("live.title")}</h4><LiveCards live={live.data} loading={live.isLoading} error={live.error as Error | null} /></section>}
          <div className="charts">
            <AreaChart d={d} />
            {!running && <ForecastChart d={d} />}
            <LstChart d={d} />
            {d.climate && <ClimateChart d={d} />}
          </div>
        </>)}
      {lake.isLoading && !!lakeId && <div className="spinner-row"><span className="spinner" /></div>}
    </aside>
  );
}
