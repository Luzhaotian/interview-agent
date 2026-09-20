import { test, expect } from '@playwright/test'

// See here how to get started:
// https://playwright.dev/docs/intro
test('visits the app root url', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: '新建对话' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '新对话' })).toBeVisible()
})
