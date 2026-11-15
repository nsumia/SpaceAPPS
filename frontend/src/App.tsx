import { NavLink, Route, Routes } from "react-router-dom";
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
        <strong className="brand">
          <svg className="brand-mark" viewBox="0 0 32 32" width="26" height="26" aria-hidden="true" focusable="false">
            <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M4.5 18c3-3 5.5-3 8 0s5 3 8 0 4-2.5 7-1" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <circle cx="22" cy="9.5" r="2.6" fill="var(--sand)" />
          </svg>
          <span className="brand-text">{t("app.title")}</span>
        </strong>
        <nav>
          <NavLink to="/" end>{t("nav.map")}</NavLink>
          <NavLink to="/compare">{t("nav.compare")}</NavLink>
          <NavLink to="/methods">{t("nav.methods")}</NavLink>
        </nav>
        <button className="lang" onClick={() => setLang(lang === "en" ? "tr" : "en")} aria-label="language">{lang === "en" ? "TR" : "EN"}</button>
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
