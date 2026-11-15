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
          <img className="brand-logo" src="/logo-64.png" width="36" height="36" alt="Augmented 6th" />
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
