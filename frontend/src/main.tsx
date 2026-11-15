import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "maplibre-gl/dist/maplibre-gl.css";
import "./fonts.css";
import "./styles.css";
import { I18nProvider } from "./i18n";
import App from "./App";

const qc = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } } });
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <I18nProvider>
        <BrowserRouter><App /></BrowserRouter>
      </I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
