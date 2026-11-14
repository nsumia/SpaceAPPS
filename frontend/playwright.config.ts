import { defineConfig } from "@playwright/test";

// Uses the system Chromium when CHROMIUM_PATH is set (no browser download needed).
// Expects the API + built frontend on http://127.0.0.1:8000 (uvicorn backend.api.main:app).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || undefined,
      args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
    },
  },
  webServer: process.env.NO_SERVER ? undefined : {
    command: "../.venv/bin/uvicorn backend.api.main:app --port 8000 --app-dir ..",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
