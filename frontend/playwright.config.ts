import { defineConfig } from "@playwright/test";

const python = process.env.E2E_PYTHON ?? (process.platform === "win32" ? ".\\venv\\Scripts\\python.exe" : "python");
export default defineConfig({
  testDir: "./e2e", fullyParallel: false, workers: 1, timeout: 60000,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://localhost:3010", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8010`, cwd: "../backend", url: "http://localhost:8010/api/health", reuseExistingServer: false, env: { ENVIRONMENT: "test", BROWSER_EXTRACTION_FIXTURE: "true", BACKEND_CORS_ORIGINS: '["http://localhost:3010"]' } },
    { command: `${python} -m scripts.browser_worker`, cwd: "../backend", wait: { stdout: /browser-fixture-ready/ }, reuseExistingServer: false, env: { ENVIRONMENT: "test" } },
    { command: "npm run dev -- --port 3010", url: "http://localhost:3010", reuseExistingServer: false, env: { NEXT_PUBLIC_API_URL: "/api", API_PROXY_ORIGIN: "http://localhost:8010" } },
  ],
});
