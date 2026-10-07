import { test, expect } from '@playwright/test';

test('dark default, keyboard switch, persistence and independent risk colors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.institution-header')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.getByLabel('어떤 위험이 있나요?', { exact: false }).fill('테마 검증용 난간 손상');
  await page.getByRole('button', { name: 'AI 위험성 분석하기', exact: true }).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  for (const theme of ['dark', 'light']) {
    if (theme === 'light') await page.getByRole('button', { name: '밝은 테마', exact: true }).press('Enter');
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    const colors = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return { brand: root.getPropertyValue('--accent'), danger: root.getPropertyValue('--risk-red'), width: document.documentElement.scrollWidth, viewport: innerWidth };
    });
    expect(colors.brand).not.toBe(colors.danger);
    expect(colors.width).toBeLessThanOrEqual(colors.viewport);
    await expect(page.locator('.evaluation-row').first().getByLabel('위험상황', { exact: true })).toBeVisible();
  }
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: '밝은 테마', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '밝은 테마', exact: true }).press('Enter');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(errors).toEqual([]);
});

test('unavailable preference storage still allows theme switching', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } }); });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: '밝은 테마', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('printing dark assessments uses paper colors and complete text', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('어떤 위험이 있나요?', { exact: false }).fill('인쇄 검증용 난간 손상');
  await page.getByRole('button', { name: 'AI 위험성 분석하기', exact: true }).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  const fullText = '긴 위험상황 인쇄 검증. '.repeat(40);
  await page.locator('.evaluation-row').first().getByLabel('위험상황', { exact: true }).fill(fullText);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(page.locator('.sidebar')).toBeHidden();
  await expect(page.getByRole('button', { name: '밝은 테마', exact: true })).toBeHidden();
  await expect(page.locator('.evaluation-row').first().locator('.print-value').nth(1)).toHaveText(fullText);
  await expect(page.locator('.evaluation-row').first().locator('.print-value').nth(1)).toBeVisible();
});
