import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: { baseURL: "http://127.0.0.1:8000" },
  webServer: {
    command: "cd .. && .venv/bin/python -m uvicorn shadow.api.app:app --app-dir backend --host 127.0.0.1 --port 8000",
    url: "http://127.0.0.1:8000/healthz",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
