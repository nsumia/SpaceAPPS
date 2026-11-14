import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../i18n";
import { useCompareIds, useLake, useLakes, useLive } from "../hooks";
import { api, ApiError } from "../lib/api";
import { summarySentence } from "../lib/summary";
import { AreaChart, ClimateChart, LstChart, VolumeChart } from "./Charts";
import { LiveCards } from "./LiveCards";
import { Link } from "react-router-dom";
import type { Job, LakeFull } from "../lib/types";

export interface Selection { id: string | null; name?: string; polygon?: GeoJSON.Geometry | null }

export function Badges({ d }: { d: LakeFull }) {
  const { t } = useI18n();
  const s = d.summary, rel = s.reliability;
  return (
    <div className="badges">
      <span className={"badge " + (s.validated ? "good" : "warn")}>{s.validated ? "✔ " : "? "}{t(s.validated ? "badge.validated" : "badge.unverified")}</span>
      <span className={"badge " + (rel === "low" ? "bad" : rel === "ok" ? "good" : "")}>{rel === "low" ? "⚠ " : ""}{t(`badge.rel.${rel === "ok" || rel === "low" ? rel : "unknown"}`)}</span>
    </div>
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

export default function Panel({ sel, onClose }: { sel: Selection; onClose: () => void }) {
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
      const body = sel.polygon && !sel.id ? { polygon: sel.polygon } : { lake_id: sel.id! };
      const r = await api.analyze(body);
      started.current = Date.now();
      setLakeId(r.lake_id ?? lakeId);
      if (r.job_id) setJobId(r.job_id); else qc.invalidateQueries({ queryKey: ["lakes"] });
    } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };

  const d = lake.data;
  const inCompare = !!d && ids.includes(d.summary.id);
  const canAnalyze = !running && (!d || (d.analysis && d.analysis.status === "failed")) && (sel.id || sel.polygon);
  return (
    <aside className="panel" data-testid="panel">
      <button className="close" onClick={onClose} aria-label={t("panel.close")}>×</button>
      <h2>{d?.summary.name ?? sel.name ?? "…"}</h2>
      {d && <Badges d={d} />}
      {d?.reliability?.note && d.summary.reliability === "low" && <div className="note bad">{d.reliability.note}</div>}
      {d && (
        <div className="actions">
          <button onClick={() => (inCompare ? remove(d.summary.id) : add(d.summary.id))} disabled={!inCompare && ids.length >= 6}>
            {inCompare ? t("panel.remove") : t("panel.add")}
          </button>
          {ids.length > 0 && <Link to="/compare" className="btn">{t("panel.compare")} ({ids.length})</Link>}
        </div>)}
      {canAnalyze && <button className="primary" onClick={start} data-testid="analyze">{sel.polygon && !sel.id ? t("an.analyze_area") : t("an.analyze")}</button>}
      {err && <div className="note bad" role="alert"><strong>{t("an.error")}:</strong> {err}</div>}
      {job.data && running && <AnalysisProgress job={job.data} started={started.current} />}
      {job.data?.status === "failed" && <div className="note bad" role="alert">{t("an.failed")}: {job.data.error}</div>}
      {running && d && <div className="note">{t("an.prelim")}</div>}
      {d?.unverified && <div className="note warn">{t("an.unverified")}</div>}
      {d && d.series.length > 0 && (
        <>
          <section><h4>{t("sum.title")}</h4><p data-testid="summary">{summarySentence(d.summary, t)}</p></section>
          {known && <section><h4>{t("live.title")}</h4><LiveCards live={live.data} loading={live.isLoading} error={live.error as Error | null} /></section>}
          <AreaChart d={d} />
          <LstChart d={d} />
          {d.climate && <ClimateChart d={d} />}
          {!d.unverified && <VolumeChart d={d} />}
        </>)}
      {lake.isLoading && !!lakeId && <div className="spinner-row"><span className="spinner" /></div>}
    </aside>
  );
}
