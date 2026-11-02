import { test, expect } from '@playwright/test';

const colors: Record<string, string> = {kywa:'#ED174F',fowi:'#00A651',knps:'#006633',knf:'#005995',kohi:'#0059A6',khidi:'#FF701E',cayf:'#507C5F',ayf:'#64748B'};
const names: Record<string,string> = {kywa:'KYWA',fowi:'FoWI',knps:'KNPS',knf:'KNF',kohi:'KOHI',khidi:'KHIDI',cayf:'CAYF',ayf:'AYF'};
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
  const analyze = page.getByRole('button', {name:`${names[institution]} AI 위험요인 분석 시작`,exact:true});
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
  await page.getByRole('button',{name:`${names[institution]} AI 위험요인 분석 시작`,exact:true}).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  await expect(page.getByRole('button',{name:`${names[institution]} AI 안전센터로 데이터 전송`,exact:true})).toBeDisabled();
});

test('지원기관 공동 표시, 개발자 팝업, 전송 및 홈 초기화', async ({page}, info) => {
  test.skip(institution === 'kywa' || !colors[institution], '지원기관 전용');
  await page.goto('/');
  await expect(page.locator('.partner-brand small')).toHaveText('한국청소년활동진흥원');
  await expect(page.getByRole('region',{name:'KYWA 기술지원'})).toContainText('시스템 구축과 운영을 지원합니다.');
  await expect(page.locator('.partner-footer')).toContainText('(Powered by KYWA)');
  await expect(page.locator('.partner-footer')).toContainText('Safe Together, KYWA AI Risk Assessment System');
  await expect(page.getByRole('heading',{name:'운영 문의'})).toHaveCount(0);
  const opener=page.getByRole('button',{name:'개발자정보',exact:true});
  await opener.click();
  const dialog=page.getByRole('dialog',{name:'개발자정보',exact:true});
  await expect(dialog).toContainText('02-6959-7138');
  await dialog.getByText('경영지원본부 안전경영부',{exact:true}).click();
  await expect(dialog).toBeVisible();
  await page.screenshot({path:info.outputPath(`${institution}-developer.png`),fullPage:false});
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0); await expect(opener).toBeFocused();
  await opener.click(); await page.mouse.click(5,5); await expect(dialog).toHaveCount(0);
  await opener.click(); await page.getByRole('button',{name:'개발자정보 닫기'}).click(); await expect(dialog).toHaveCount(0);
  const name=page.getByLabel('제출자 성명',{exact:true});
  await name.fill('홍길동');
  await expect(page.getByText('홍㉠㉢으로 제출됩니다.',{exact:true})).toBeVisible();
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill('시험용 난간 흔들림');
  await page.getByRole('button',{name:`${names[institution]} AI 위험요인 분석 시작`,exact:true}).click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  const submit=page.getByRole('button',{name:`${names[institution]} AI 안전센터로 데이터 전송`,exact:true});
  await expect(submit).toBeEnabled();
  const ratio=await submit.evaluate(el=>el.getBoundingClientRect().width/el.parentElement!.getBoundingClientRect().width);
  expect(ratio).toBeGreaterThanOrEqual(0.49);
  await page.screenshot({path:info.outputPath(`${institution}-result.png`),fullPage:true});
  await submit.click();
  await expect(page.locator('.progress-dialog [role="status"]')).toContainText('1건을 제출했습니다');
  await expect(page.locator('.progress-dialog')).toBeHidden();
  await page.locator('a.brand').click();
  await expect(name).toHaveValue('');
  await expect(page.locator('.evaluation-row')).toHaveCount(0);
});
