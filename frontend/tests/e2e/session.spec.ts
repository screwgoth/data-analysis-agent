import { test, expect } from '@playwright/test'
import path from 'node:path'

// ---------------------------------------------------------------------------
// Phase 2 primary-journey E2E: conversation session, suggestions, clarifying
// flow inputs, interactive chart, sortable table, and token badge.
//
// PREREQUISITE: a LIVE server on :8001 serving the built static export at
// /app/ AND the real FastAPI backend under /api (with a real Gemini key in
// `.env`). This test does NOT start a server. The gate runs:
//     cd frontend && pnpm build
//     uv run python -m src            # serves /app + /api on :8001
//     npx playwright test frontend/tests/e2e/ --reporter=line
//
// Assertions are on SHAPE and PRESENCE (real numbers, a rendered chart, chips,
// a token count), NEVER on exact model prose.
// ---------------------------------------------------------------------------

// Playwright's loader runs specs as CommonJS, so `__dirname` is available.
const FIXTURE = path.join(__dirname, '..', 'fixtures', 'sales.csv')

// Three real LLM analyses run in this journey; give the whole test ample room.
test.setTimeout(540_000)

async function waitForLatestAnswer(page: import('@playwright/test').Page, expectedTurns: number) {
  // Every turn's answer eventually renders its prose block.
  await expect(page.getByTestId('answer-prose')).toHaveCount(expectedTurns, { timeout: 180_000 })
}

test('session: multi-turn transcript, suggestions, chart, token badge', async ({ page }) => {
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: /Local Data Analysis Agent/i })).toBeVisible()

  // Phase-3 features are now live — the library sidebar is real, no stubs.
  await expect(page.getByRole('heading', { name: /Dataset library/i })).toBeVisible()
  await expect(page.getByText(/Coming soon/i)).toHaveCount(0)

  // --- Upload the real CSV, wait for the profile ---
  await page.setInputFiles('input[type="file"]', FIXTURE)
  await expect(page.getByRole('heading', { name: /Profile/i })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('cell', { name: 'region', exact: true })).toBeVisible()

  // --- Turn 1: a breakdown question that should yield a chart ---
  await page.getByLabel(/Your question about the data/i).fill(
    'What is the total revenue by region?',
  )
  await page.getByRole('button', { name: /^Ask$/ }).click()
  await expect(page.getByText(/Analyzing/i).first()).toBeVisible()

  await waitForLatestAnswer(page, 1)

  // The transcript keeps the question bubble.
  await expect(page.getByTestId('turn-question').first()).toContainText(/revenue by region/i)

  // The first answer contains at least one real number.
  const firstAnswer = (await page.getByTestId('answer-prose').first().innerText()).trim()
  expect(firstAnswer).toMatch(/\d/)

  // Interactive chart rendered for the breakdown.
  await expect(page.getByTestId('chart').first()).toBeVisible({ timeout: 20_000 })

  // Token badge shows a token count (never a dollar cost).
  const badge = page.getByTestId('token-badge').first()
  await expect(badge).toBeVisible()
  await expect(badge).toContainText(/tokens/i)
  await expect(badge).not.toContainText('$')

  // 2–3 clickable follow-up suggestion chips appear.
  const chips = page.getByTestId('suggestion-chip')
  const chipCount = await chips.count()
  expect(chipCount).toBeGreaterThanOrEqual(2)
  expect(chipCount).toBeLessThanOrEqual(4)

  // --- Turn 2: a typed, scoped follow-up (resolves against session history) ---
  await page.getByLabel(/Your question about the data/i).fill('and just for the North region?')
  await page.getByRole('button', { name: /^Ask$/ }).click()
  await waitForLatestAnswer(page, 2)

  // BOTH turns remain visible in the transcript.
  await expect(page.getByTestId('turn')).toHaveCount(2)
  await expect(page.getByTestId('turn-question').nth(1)).toContainText(/North region/i)
  // The follow-up produced its own answer with content.
  const secondAnswer = (await page.getByTestId('answer-prose').nth(1).innerText()).trim()
  expect(secondAnswer.length).toBeGreaterThan(10)

  // --- Turn 3: click a suggestion chip → submits a new turn ---
  await page.getByTestId('suggestion-chip').last().click()
  await expect(page.getByText(/Analyzing/i).first()).toBeVisible()
  await waitForLatestAnswer(page, 3)
  await expect(page.getByTestId('turn')).toHaveCount(3)

  // The library sidebar is still present at the end; no coming-soon stubs.
  await expect(page.getByRole('heading', { name: /Dataset library/i })).toBeVisible()
  await expect(page.getByText(/Coming soon/i)).toHaveCount(0)
})
