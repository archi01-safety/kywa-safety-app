import { test, expect } from '@playwright/test';

test('department counts use the facility chart title and follow the selected year', async ({ page }) => {
  const year = new Date().getFullYear();
  await page.route(/\/api\/overview\?/, async (route) => {
    const currentYear = Number(new URL(route.request().url()).searchParams.get('year'));
    const current = currentYear === year;
    await route.fulfill({ json: {
      year: currentYear,
      years: [year, year - 1],
      total: current ? 3 : 0,
      completed: 0,
      facility_count: current ? 1 : 0,
      categories: current ? [{ name: '시설 안전', count: 3 }] : [],
      facilities: [{ name: '국립공원공단', count: current ? 3 : 0 }],
      departments: current ? [{ name: '본사', count: 2 }, { name: '동부지역본부', count: 1 }] : [],
    } });
  });

  await page.goto('/');
  const chart = page.locator('.count-chart').filter({ has: page.getByRole('heading', { name: '시설별 평가 현황', exact: true }) });
  await expect(chart.getByRole('listitem')).toHaveCount(2);
  await expect(chart.getByRole('listitem').filter({ hasText: '본사' })).toContainText('2건');
  await expect(chart.getByRole('listitem').filter({ hasText: '동부지역본부' })).toContainText('1건');
  await expect(chart).not.toContainText('국립공원공단');

  await page.getByLabel('조회 연도').selectOption(String(year - 1));
  await expect(chart).toContainText('선택한 연도의 평가가 없습니다.');
});
