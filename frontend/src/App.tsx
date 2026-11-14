import { NavLink, Route, Routes } from "react-router-dom";
import { useI18n } from "./i18n";
import MapPage from "./pages/MapPage";
import ComparePage from "./pages/ComparePage";
import MethodsPage from "./pages/MethodsPage";

export default function App() {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="app">
      <header className="top">
        <strong className="brand">{t("app.title")}</strong>
        <nav>
          <NavLink to="/" end>{t("nav.map")}</NavLink>
          <NavLink to="/compare">{t("nav.compare")}</NavLink>
          <NavLink to="/methods">{t("nav.methods")}</NavLink>
        </nav>
        <button className="lang" onClick={() => setLang(lang === "en" ? "tr" : "en")} aria-label="language">{lang === "en" ? "TR" : "EN"}</button>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<MapPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/methods" element={<MethodsPage />} />
          <Route path="*" element={<MapPage />} />
        </Routes>
      </main>
    </div>
  );
}
