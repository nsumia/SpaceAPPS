import { Link, NavLink, Route, Routes } from "react-router-dom";
import { useI18n } from "./i18n";
import { lazy, Suspense } from "react";

// Route-level code splitting: the map (maplibre), compare (ECharts) and methods pages load on first visit.
const MapPage = lazy(() => import("./pages/MapPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const MethodsPage = lazy(() => import("./pages/MethodsPage"));

export default function App() {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="app">
      <header className="top">
        <a className="skip" href="#main">{t("nav.skip")}</a>
        <Link to="/" className="brand" aria-label={t("app.title")}>
          <svg className="brand-mark" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
            <path d="M16 3.5c5.6 0 11.5 4.3 12 10.6.5 6.6-4.8 14.4-12.4 14.4S3.4 22.4 4.3 15.6C5.1 8.6 10.4 3.5 16 3.5z" fill="currentColor" opacity=".22" />
            <path d="M16 3.5c5.6 0 11.5 4.3 12 10.6.5 6.6-4.8 14.4-12.4 14.4S3.4 22.4 4.3 15.6C5.1 8.6 10.4 3.5 16 3.5z" fill="none" stroke="currentColor" strokeWidth="1.8" />
            <path d="M16.2 9c3.5.2 6.8 2.9 6.9 6.6.1 4-3 7.4-7 7.2-3.8-.2-6.2-3.5-5.7-7C10.9 12 12.7 8.8 16.2 9z" fill="none" stroke="var(--red-lt)" strokeWidth="1.6" strokeDasharray="2.6 2.2" />
            <circle cx="16" cy="16" r="2.4" fill="var(--red-lt)" />
          </svg>
          <span className="brand-text">
            <span className="brand-name">{t("app.title")}</span>
            <span className="brand-sub">{t("app.sub")}</span>
          </span>
        </Link>
        <nav aria-label={t("nav.main")}>
          <NavLink to="/" end>{t("nav.map")}</NavLink>
          <NavLink to="/compare">{t("nav.compare")}</NavLink>
          <NavLink to="/methods">{t("nav.methods")}</NavLink>
        </nav>
        <button className="lang" onClick={() => setLang(lang === "en" ? "tr" : "en")} aria-label={t("nav.lang")}>
          <span className={lang === "tr" ? "on" : ""} aria-hidden="true">TR</span>
          <span className={lang === "en" ? "on" : ""} aria-hidden="true">EN</span>
        </button>
      </header>
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<div className="spinner-row" role="status"><span className="spinner" /></div>}>
        <Routes>
          <Route path="/" element={<MapPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/methods" element={<MethodsPage />} />
          <Route path="*" element={<MapPage />} />
        </Routes>
        </Suspense>
      </main>
    </div>
  );
}
