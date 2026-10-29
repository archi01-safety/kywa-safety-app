import { test, expect } from '@playwright/test';

const colors: Record<string, string> = {kywa:'#ED174F',fowi:'#00A651',knps:'#006633',knf:'#005995',kohi:'#0059A6',khidi:'#FF701E',cayf:'#507C5F',ayf:'#64748B'};
const institution = process.env.ORGANIZATION_ID || 'kywa';

test('기관색 로딩, 버튼 상태, 의미 색상, 모바일 및 테마 전환', async ({page}, info) => {
  test.skip(!colors[institution], '실제 기관 설정 전용');
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/bootstrap', async route => { await pending; await route.continue(); });
  await page.goto('/');
  const brand = () => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--brand-original').trim());
  expect(await brand()).toBe('#64748B');
  release();
  await expect.poll(brand).toBe(colors[institution]);
  const analyze = page.getByRole('button', {name:'AI 위험성 분석하기',exact:true});
  await expect(analyze).toBeDisabled();
  await page.getByLabel('제출자 성명',{exact:true}).fill('홍길동');
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill('시험용 난간 손상');
  await expect(analyze).toBeEnabled();
  if (institution !== 'kywa') await expect(page.locator('.brand img')).toHaveCount(0);
  for (const theme of ['dark','light']) {
    if (theme==='light') await page.getByRole('button',{name:'밝은 테마',exact:true}).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
    await page.mouse.move(0,0);
    const original=await page.evaluate(()=>{
      const color=getComputedStyle(document.documentElement).getPropertyValue('--brand-button').trim();
      return `rgb(${[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)).join(', ')})`;
    });
    await expect(analyze).toHaveCSS('background-color',original);
    await analyze.hover();
    await expect.poll(()=>analyze.evaluate(el=>getComputedStyle(el).backgroundColor)).not.toBe(original);
    const state=await page.evaluate(()=>{
      const root=getComputedStyle(document.documentElement);
      return {risk:root.getPropertyValue('--risk-red'),accent:root.getPropertyValue('--accent'),
        overflow:document.documentElement.scrollWidth>innerWidth};
    });
    expect(state.risk).not.toBe(state.accent);
    expect(state.overflow).toBe(false);
    await page.screenshot({path:info.outputPath(`${institution}-${theme}.png`),fullPage:true});
  }
  await analyze.click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  await expect(page.locator('.evaluation-row .badge')).not.toHaveClass(/tone--1/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('AYF 저장소 준비 안내와 제출 차단', async ({page}) => {
  test.skip(institution !== 'ayf', 'AYF 준비 모드 전용');
  await page.route('**/api/bootstrap', async route => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({response, json:{...body, mode:'setup'}});
  });
  await page.goto('/');
  await expect(page.getByText('저장소 준비 중',{exact:true})).toBeVisible();
  await expect(page.getByText('저장소 연결 준비 중',{exact:true})).toBeVisible();
  await page.getByLabel('제출자 성명',{exact:true}).fill('홍길동');
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill('가상 시험: 난간 파손');
  await page.getByRole('button',{name:'AI 위험성 분석하기',exact:true}).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  await expect(page.getByRole('button',{name:'선택한 평가 제출',exact:true})).toBeDisabled();
});
