import { defineConfig, devices } from '@playwright/test'

// E2E runs against the ALREADY-RUNNING single-origin app.
// The gate builds the static export (`pnpm build`) and starts the backend
// (`uv run python -m src`) on :8001, which serves the export at /app/.
// We do NOT start a webServer here — the app is expected to be up.
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8001'

export default defineConfig({
  testDir: './tests/e2e',
  // Real LLM analysis is synchronous and can take a while.
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
