import { test, expect } from '@playwright/test';

test('evaluation, reassessment, completion, history and reports', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByText('체험 환경', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI 위험성 분석하기', exact: true })).toBeDisabled();
  const location = `${info.project.name} 자동 검증 2층 난간`;
  await page.getByLabel('어떤 위험이 있나요?', { exact: false }).fill('2층 난간 손상\n바닥 미끄러움');
  await page.getByRole('button', { name: 'AI 위험성 분석하기', exact: true }).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.locator('.evaluation-row').first().getByLabel('장소', { exact: true }).fill(location);
  await page.getByRole('checkbox', { name: '02 · 시설 안전' }).uncheck();
  await page.getByRole('button', { name: '선택한 평가 제출', exact: true }).click();
  await expect(page.locator('.message[role="status"]')).toContainText('1건을 제출했습니다');
  await page.getByRole('button', { name: '개선조치 · 재평가', exact: true }).click();
  await page.getByRole('button', { name: '관리자로 체험하기', exact: true }).click();
  await page.getByRole('button').filter({ has: page.getByRole('heading', { name: location, exact: true }) }).click();
  await page.getByLabel('실제 조치내용', { exact: true }).fill('손상 부위를 보수하고 재점검했습니다.');
  await page.getByRole('button', { name: 'AI 재평가하기', exact: true }).click();
  await page.getByRole('combobox', { name: '빈도', exact: true }).selectOption('1');
  await page.getByRole('button', { name: '확인 후 완료', exact: true }).click();
  await expect(page.getByText('개선조치가 완료되었습니다.', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '변경 이력 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '다시 열기', exact: true }).click();
  await expect(page.getByRole('heading', { name: '변경 이력 2', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '결과보고서', exact: true }).click();
  for (const format of ['Excel', 'PDF']) {
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: new RegExp(`${format} 다운로드`) }).click();
    const file = await download;
    expect(await file.failure()).toBeNull();
    await file.saveAs(info.outputPath(`report.${format === 'Excel' ? 'xlsx' : 'pdf'}`));
  }
  await page.reload();
  await expect(page.getByRole('heading', { name: '우리의 안전, 한눈에 확인하세요.', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: info.outputPath('reports.png'), fullPage: true });
  await page.getByRole('button', { name: info.project.name === 'mobile' ? '현재 계정 로그아웃' : '로그아웃', exact: true }).click();
  await expect(page.getByRole('heading', { name: '담당자 로그인', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '중앙 담당자로 체험하기', exact: true }).click();
  await expect(page.getByText('결과보고서는 관리자 계정으로 이용할 수 있습니다.', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
