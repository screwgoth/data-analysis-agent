import { test, expect } from '@playwright/test'
import path from 'node:path'

// ---------------------------------------------------------------------------
// Phase 3 primary-journey E2E: the persistent dataset library, multi-select,
// rename/delete, and result export.
//
// PREREQUISITE: a LIVE server on :8001 serving the built static export at
// /app/ AND the real FastAPI backend under /api (with a real Gemini key in
// `.env`). This test does NOT start a server. The gate runs:
//     cd frontend && pnpm build
//     uv run python -m src            # serves /app + /api on :8001
//     npx playwright test frontend/tests/e2e/ --reporter=line
//
// Assertions are on RENDERED CONTENT (library rows, persisted names, a real
// download), not just HTTP status. Multi-file JOIN and xlsx/pdf upload need
// backend fixtures to be deterministic, so here we assert the multi-select UI
// and export controls EXIST and that the library PERSISTS across a reload.
// ---------------------------------------------------------------------------

// Playwright's loader runs specs as CommonJS, so `__dirname` is available.
const FIXTURE = path.join(__dirname, '..', 'fixtures', 'sales.csv')

// Real LLM analysis is synchronous and can take a while.
test.setTimeout(300_000)

test('library: upload persists, rename persists, ask, export downloads', async ({ page }) => {
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: /Local Data Analysis Agent/i })).toBeVisible()

  // The library sidebar is a real feature now — no coming-soon stubs anywhere.
  await expect(page.getByRole('heading', { name: /Dataset library/i })).toBeVisible()
  await expect(page.getByText(/Coming soon/i)).toHaveCount(0)

  // --- Upload the real CSV ---
  await page.setInputFiles('input[type="file"]', FIXTURE)

  // Profile renders (upload succeeded) ...
  await expect(page.getByRole('heading', { name: /Profile/i })).toBeVisible({ timeout: 30_000 })

  // ... and the dataset now appears in the library sidebar with a format badge.
  const items = page.getByTestId('library-item')
  await expect(items.first()).toBeVisible()
  await expect(page.getByTestId('library-item-name').filter({ hasText: /sales/i }).first()).toBeVisible()
  await expect(page.getByTestId('format-badge').first()).toBeVisible()

  const countBeforeReload = await items.count()
  expect(countBeforeReload).toBeGreaterThan(0)

  // --- Reload: the library PERSISTS because it reads from the backend ---
  await page.reload()
  await expect(page.getByRole('heading', { name: /Dataset library/i })).toBeVisible()
  await expect(page.getByTestId('library-item')).toHaveCount(countBeforeReload)
  await expect(
    page.getByTestId('library-item-name').filter({ hasText: /sales/i }).first(),
  ).toBeVisible()

  // --- Rename the dataset inline; the new name persists across a reload ---
  const uniqueName = `renamed_${Date.now()}`
  // Rename the first item.
  await page.getByTestId('rename-button').first().click()
  const renameInput = page.getByTestId('rename-input')
  await expect(renameInput).toBeVisible()
  await renameInput.fill(uniqueName)
  await renameInput.press('Enter')

  await expect(
    page.getByTestId('library-item-name').filter({ hasText: uniqueName }).first(),
  ).toBeVisible({ timeout: 15_000 })

  await page.reload()
  await expect(
    page.getByTestId('library-item-name').filter({ hasText: uniqueName }).first(),
  ).toBeVisible({ timeout: 15_000 })

  // --- Select the dataset and ask a question ---
  await page.getByTestId('library-item-name').filter({ hasText: uniqueName }).first().click()
  // The active-datasets banner confirms the selection is wired to the query.
  await expect(page.getByTestId('active-datasets')).toBeVisible()
  // Multi-select checkboxes exist (the cross-file selector UI).
  await expect(page.locator('input[type="checkbox"]').first()).toBeVisible()

  await page.getByLabel(/Your question about the data/i).fill(
    'What is the total revenue by region?',
  )
  await page.getByRole('button', { name: /^Ask$/ }).click()
  await expect(page.getByText(/Analyzing/i).first()).toBeVisible()

  // --- Answer renders, and its Export control is present ---
  await expect(page.getByTestId('answer-prose')).toBeVisible({ timeout: 180_000 })
  const exportMenu = page.getByTestId('export-menu').first()
  await expect(exportMenu).toBeVisible()
  await expect(page.getByTestId('export-csv').first()).toBeVisible()
  await expect(page.getByTestId('export-xlsx').first()).toBeVisible()

  // --- Trigger a real CSV download and assert it initiates ---
  const downloadPromise = page.waitForEvent('download')
  await page.getByTestId('export-csv').first().click()
  const download = await downloadPromise
  expect(download.suggestedFilename().length).toBeGreaterThan(0)

  // Still no coming-soon stubs anywhere at the end of the journey.
  await expect(page.getByText(/Coming soon/i)).toHaveCount(0)
})
