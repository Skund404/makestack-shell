/**
 * Kitchen module E2E tests — covers the full user journey for recipes,
 * stock management, cook log, and meal planning.
 *
 * Prerequisites:
 *   - Shell running on http://localhost:9000 with kitchen module loaded
 *   - Core running and connected
 *   - At least 1 stock item and 1 recipe exist
 */
import { test, expect, type Page } from '@playwright/test'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Navigate to a kitchen route and wait for content to load. */
async function goKitchen(page: Page, path = '/kitchen') {
  await page.goto(path)
  // Wait for the Kitchen sidebar to render (app mode)
  await page.waitForSelector('a:has-text("Home")', { timeout: 10_000 })
}

// ---------------------------------------------------------------------------
// 1. Recipe CRUD journey (single test for state continuity)
// ---------------------------------------------------------------------------

test('recipe CRUD: create, verify, edit, delete', async ({ page }) => {
  const recipeTitle = `Playwright Recipe ${Date.now()}`

  // --- CREATE ---
  await goKitchen(page, '/kitchen/recipes')
  await page.click('[data-testid="new-recipe-btn"]')
  await page.waitForURL('**/kitchen/recipes/new')

  await page.fill('[data-testid="recipe-title-input"]', recipeTitle)
  await page.fill('textarea >> nth=0', 'A test recipe created by Playwright')

  // Add a step
  await page.click('text=Add step')
  await page.locator('textarea').last().fill('Mix everything together')

  await page.click('[data-testid="recipe-save-btn"]')
  await page.waitForTimeout(1500)

  // --- VERIFY in list ---
  await goKitchen(page, '/kitchen/recipes')
  await page.waitForTimeout(1500)

  const recipeBtn = page.locator(`button:has-text("${recipeTitle}")`)
  await expect(recipeBtn).toBeVisible({ timeout: 10_000 })

  // --- EDIT ---
  await recipeBtn.click()
  await page.waitForTimeout(500)

  await page.click('[data-testid="recipe-edit-btn"]')
  await page.waitForURL('**/kitchen/recipes/*/edit')

  const titleInput = page.locator('[data-testid="recipe-title-input"]')
  await titleInput.fill(`${recipeTitle} Edited`)
  await page.click('[data-testid="recipe-save-btn"]')
  await page.waitForTimeout(1500)

  // Verify edited title appears
  await goKitchen(page, '/kitchen/recipes')
  await page.waitForTimeout(1500)
  await expect(page.locator(`button:has-text("${recipeTitle} Edited")`)).toBeVisible({ timeout: 10_000 })

  // --- DELETE ---
  await page.click(`button:has-text("${recipeTitle} Edited")`)
  await page.waitForTimeout(500)

  page.on('dialog', (d) => d.accept())
  await page.click('[data-testid="recipe-delete-btn"]')
  await page.waitForTimeout(2000)

  // Re-navigate to force fresh list
  await goKitchen(page, '/kitchen/recipes')
  await page.waitForTimeout(1500)

  // Verify deleted
  await expect(page.locator(`button:has-text("${recipeTitle} Edited")`)).toHaveCount(0, { timeout: 5000 })
})

// ---------------------------------------------------------------------------
// 2. Stock item edit (Larder)
// ---------------------------------------------------------------------------

test('larder: click stock item opens edit panel, save changes', async ({ page }) => {
  await goKitchen(page, '/kitchen/larder')
  await page.waitForTimeout(1500)

  // Find a stock item row (they have cursor-pointer class)
  const items = page.locator('[class*="cursor-pointer"][class*="border-b"]')
  const count = await items.count()
  if (count === 0) {
    test.skip()
    return
  }

  // Click first item
  await items.first().click()
  await page.waitForTimeout(500)

  // Edit panel should appear
  const editHeader = page.getByText('Edit Item', { exact: true })
  await expect(editHeader).toBeVisible({ timeout: 3000 })

  // Modify quantity
  const qtyInputs = page.locator('input[type="number"]')
  const qtyInput = qtyInputs.first()
  const currentQty = await qtyInput.inputValue()
  const newQty = (parseFloat(currentQty) + 0.5).toString()
  await qtyInput.fill(newQty)

  // Save
  await page.click('[data-testid="stock-save-btn"]')
  await page.waitForTimeout(1000)

  // Panel should close
  await expect(editHeader).toBeHidden({ timeout: 3000 })
})

// ---------------------------------------------------------------------------
// 3. Larder add item panel
// ---------------------------------------------------------------------------

test('larder: add item panel opens and closes', async ({ page }) => {
  await goKitchen(page, '/kitchen/larder')
  await page.waitForTimeout(500)

  // Click "Add item" button in the search bar
  await page.getByRole('button', { name: 'Add item' }).click()
  await page.waitForTimeout(300)

  // Panel header "Add Item" should appear (the <p> inside the panel)
  const panelHeader = page.locator('p:has-text("Add Item")').first()
  await expect(panelHeader).toBeVisible({ timeout: 3000 })

  // Close the panel via the X button next to "Add Item"
  // The X button is in the same parent div as the "Add Item" header
  const closeBtn = panelHeader.locator('..').locator('button')
  await closeBtn.click()
  await page.waitForTimeout(300)
})

// ---------------------------------------------------------------------------
// 4. Cook log record
// ---------------------------------------------------------------------------

test('cook log: record a session', async ({ page }) => {
  await goKitchen(page, '/kitchen/cook-log')
  await page.waitForTimeout(500)

  await page.click('[data-testid="record-cook-btn"]')
  await page.waitForTimeout(300)

  // Select recipe
  const select = page.locator('[data-testid="cook-recipe-select"]')
  await expect(select).toBeVisible()
  const options = select.locator('option')
  const optionCount = await options.count()
  if (optionCount < 2) {
    test.skip()
    return
  }
  const firstValue = await options.nth(1).getAttribute('value')
  await select.selectOption(firstValue!)

  // Save
  await page.click('[data-testid="cook-save-btn"]')
  await page.waitForTimeout(1500)

  // Should see at least one cook log entry
  const entries = page.locator('.rounded.border.border-border.bg-surface')
  await expect(entries.first()).toBeVisible({ timeout: 5000 })
})

// ---------------------------------------------------------------------------
// 5. Meal plan edit + clear
// ---------------------------------------------------------------------------

test('meal plan: set free-text entry and clear it', async ({ page }) => {
  await goKitchen(page, '/kitchen/meal-plan')
  await page.waitForTimeout(1500)

  // Click an empty cell (shown as "—")
  const emptyCell = page.locator('span:text-is("—")').first()
  const emptyCellCount = await emptyCell.count()
  if (emptyCellCount === 0) {
    test.skip()
    return
  }
  // Click the parent div of the dash (the clickable cell)
  await emptyCell.locator('..').click()
  await page.waitForTimeout(500)

  // Switch to Free text mode
  const freeTextBtn = page.getByRole('button', { name: 'Free text' })
  if (await freeTextBtn.isVisible()) {
    await freeTextBtn.click()
    await page.waitForTimeout(200)
  }

  // Type meal text
  const input = page.locator('input[placeholder="e.g. Leftovers"]')
  if (await input.isVisible()) {
    await input.fill('E2E Test Meal')
  }

  // Save
  await page.getByRole('button', { name: 'Save' }).last().click()
  await page.waitForTimeout(1500)

  // Verify it appeared
  const mealEntry = page.locator('text=E2E Test Meal')
  await expect(mealEntry).toBeVisible({ timeout: 5000 })

  // Click to reopen and clear
  await mealEntry.click()
  await page.waitForTimeout(500)

  const clearBtn = page.getByRole('button', { name: 'Clear' })
  if (await clearBtn.isVisible()) {
    await clearBtn.click()
    await page.waitForTimeout(1500)
    await expect(mealEntry).toBeHidden({ timeout: 5000 })
  }
})

// ---------------------------------------------------------------------------
// 6. Navigation: sidebar links
// ---------------------------------------------------------------------------

test('kitchen sidebar navigation works', async ({ page }) => {
  await goKitchen(page, '/kitchen')

  // Navigate to Larder
  await page.click('a:has-text("Larder")')
  await expect(page).toHaveURL(/\/kitchen\/larder/)
  await expect(page.getByRole('heading', { name: 'Larder' })).toBeVisible()

  // Navigate to Recipes
  await page.click('a:has-text("Recipes")')
  await expect(page).toHaveURL(/\/kitchen\/recipes/)
  await expect(page.getByRole('heading', { name: 'Recipes' })).toBeVisible()

  // Navigate to Plan
  await page.click('a:has-text("Plan")')
  await expect(page).toHaveURL(/\/kitchen\/meal-plan/)
  await expect(page.getByRole('heading', { name: 'Meal Plan' })).toBeVisible()

  // Navigate to Shop
  await page.click('a:has-text("Shop")')
  await expect(page).toHaveURL(/\/kitchen\/shopping/)

  // Navigate Home
  await page.click('a:has-text("Home")')
  await expect(page).toHaveURL(/\/kitchen$/)
})
