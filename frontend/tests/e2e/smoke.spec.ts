import { test, expect } from '@playwright/test'
import path from 'node:path'

// ---------------------------------------------------------------------------
// Phase 1 primary-journey smoke test.
//
// PREREQUISITE: a LIVE server on :8001 serving the built static export at
// /app/ AND the real FastAPI backend under /api (with a real Gemini key in
// `.env`). This test does NOT start a server. The gate runs:
//     cd frontend && pnpm build
//     uv run python -m src            # serves /app + /api on :8001
//     npx playwright test frontend/tests/e2e/ --reporter=line
//
// Assertions are on SHAPE and PRESENCE (real numbers, real pandas code),
// never on exact model prose.
// ---------------------------------------------------------------------------

// Playwright's loader runs specs as CommonJS, so `__dirname` is available.
const FIXTURE = path.join(__dirname, '..', 'fixtures', 'sales.csv')

test('upload → profile → ask → answer with code trace', async ({ page }) => {
  await page.goto('/app/')

  // Page loaded and styled (header present).
  await expect(page.getByRole('heading', { name: /Local Data Analysis Agent/i })).toBeVisible()

  // The persistent library sidebar is present and real (no coming-soon stubs).
  await expect(page.getByRole('heading', { name: /Dataset library/i })).toBeVisible()
  await expect(page.getByText(/Coming soon/i)).toHaveCount(0)

  // --- Upload the real CSV ---
  await page.setInputFiles('input[type="file"]', FIXTURE)

  // --- Profile renders with column names + a PII badge ---
  await expect(page.getByRole('heading', { name: /Profile/i })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('cell', { name: 'region', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'revenue', exact: true })).toBeVisible()
  // rep_email column should be flagged PII.
  await expect(page.getByTestId('pii-badge').first()).toBeVisible()

  // --- Ask a quantitative question ---
  await page.getByLabel(/Your question about the data/i).fill(
    'What is the total revenue by region?',
  )
  await page.getByRole('button', { name: /^Ask$/ }).click()

  // Spinner acknowledges the long-running analysis.
  await expect(page.getByText(/Analyzing/i).first()).toBeVisible()

  // --- Answer renders with real content ---
  const prose = page.getByTestId('answer-prose')
  await expect(prose).toBeVisible({ timeout: 110_000 })
  const answerText = (await prose.innerText()).trim()
  expect(answerText.length).toBeGreaterThan(20)
  // The answer should contain at least one number (a key figure).
  expect(answerText).toMatch(/\d/)

  // --- Show code reveals real pandas ---
  const toggle = page.getByTestId('show-code-toggle')
  await expect(toggle).toBeVisible()
  await toggle.click()

  const trace = page.getByTestId('code-trace')
  await expect(trace).toBeVisible()
  const firstCode = page.getByTestId('step-code').first()
  await expect(firstCode).toBeVisible()
  const codeText = (await firstCode.innerText()).trim()
  expect(codeText.length).toBeGreaterThan(0)
  // Real pandas analysis references the dataframe.
  expect(codeText.toLowerCase()).toContain('df')
})
