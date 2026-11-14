import { useState } from "react";
import { useI18n } from "../i18n";
import type { Live, LiveCard } from "../lib/types";

const num = (x: unknown, d = 1) => (typeof x === "number" ? x.toFixed(d) : "-");

function Card({ title, card, children, date }: { title: string; card?: LiveCard; children?: React.ReactNode; date?: string }) {
  const { t } = useI18n();
  const ok = card?.ok;
  return (
    <div className="card" data-testid="live-card">
      <div className="card-h">
        <span>{title}</span>
        {card?.cached && <span className="tag" data-testid="cache-tag">{t("live.cache")}</span>}
        {card?.stale && <span className="tag warn">{t("live.stale")}</span>}
      </div>
      {ok ? <div className="card-v">{children}</div> : <div className="card-v muted">{t("live.nodata")}{card?.error ? <div className="small">{card.error}</div> : null}</div>}
      <div className="src small">
        {t("live.source")}: {card?.source ?? "-"}{date ? <> | {t("live.data")}: {date}</> : null}
        {card?.refresh_error ? <div>{card.refresh_error}</div> : null}
      </div>
    </div>
  );
}

function Snapshot({ card }: { card?: LiveCard }) {
  const { t } = useI18n();
  const live = typeof card?.image_url === "string" ? card.image_url : null;
  const snap = typeof card?.snapshot_url === "string" ? card.snapshot_url : null;
  const [src, setSrc] = useState(live ?? snap);
  if (!src) return null;
  return (
    <div className="card" data-testid="gibs-card">
      <div className="card-h"><span>{t("live.snapshot")}</span>{src === snap && <span className="tag" data-testid="cache-tag">{t("live.cache")}</span>}</div>
      <img src={src} alt="VIIRS" style={{ width: "100%", borderRadius: 4 }} onError={() => { if (snap && src !== snap) setSrc(snap); else setSrc(null); }} />
      <div className="src small">{t("live.source")}: {card?.source ?? "NASA GIBS"}</div>
    </div>
  );
}

export function LiveCards({ live, loading, error }: { live?: Live; loading: boolean; error?: Error | null }) {
  const { t } = useI18n();
  if (loading) return <div className="spinner-row" role="status"><span className="spinner" /> {t("live.loading")}</div>;
  if (error || !live) return <div className="note">{t("live.unavailable")}{error ? `: ${error.message}` : ""}</div>;
  const c = live.cards;
  const l = c.landsat, s = c.swot, p = c.precip;
  const latest = typeof l?.latest_scene === "string" ? l.latest_scene : undefined;
  return (
    <div className="cards">
      <Card title={t("live.area")} card={l} date={latest}>
        <b>{num(l?.area_km2)}</b> km2
        <div className="small">{t("live.vsly")}: {num(l?.change_vs_last_year_pct)}%</div>
      </Card>
      <Card title={t("live.lst")} card={l} date={latest}>
        <b>{num(l?.lst_c)}</b> C
        <div className="small">{t("live.vsly")}: {num(l?.lst_change_vs_last_year_c)} C</div>
      </Card>
      <Card title={t("live.swot")} card={s} date={typeof s?.last_obs === "string" ? s.last_obs : undefined}>
        <b>{num(s?.wse_m, 2)}</b> m
        <div className="small">1 y: {num(s?.wse_change_1y_m, 2)} m</div>
      </Card>
      <Card title={t("live.precip")} card={p} date={typeof p?.data_until === "string" ? p.data_until : undefined}>
        <b>{num(p?.precip_mm, 0)}</b> mm
        <div className="small">{String(p?.pct_of_normal ?? "-")}% {t("live.ofnormal")}</div>
      </Card>
      <Snapshot card={c.gibs} />
    </div>
  );
}
