import { test, expect } from '@playwright/test';

test('name preview, required gating, IME, private requests and admin displays', async ({page}, info) => {
  test.skip(process.env.ORGANIZATION_ID === 'example', 'KYWA default configuration');
  const requests: {url:string; body:string}[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/')) requests.push({url:request.url(),body:request.postData() || ''});
  });
  await page.goto('/');
  const input = page.getByLabel('제출자 성명', {exact:true});
  const preview = page.locator('#submitter-name-preview');
  const analyze = page.getByRole('button', {name:'KYWA AI 위험요인 분석 시작', exact:true});
  await expect(page.locator('.input-panel').getByLabel('제출자 성명', {exact:true})).toBeVisible();
  await page.getByLabel('어떤 위험이 있나요?', {exact:false}).fill('시험용 난간 손상');
  await expect(analyze).toBeDisabled();
  for (const [raw, masked] of [['홍','홍'],['김민','김㉤'],['남궁민','남㉠㉤'],['김하늘별','김㉭㉡㉥'],['홍까따빠싸짜','홍ㄲㄸㅃㅆㅉ'],[' 홍 길 동 ','홍㉠㉢'],['홍길동'.normalize('NFD'),'홍㉠㉢']]) {
    await input.fill(raw);
    await expect(input).toHaveValue(raw);
    await expect(preview).toHaveText(`${masked}으로 제출됩니다.`);
    await expect(analyze).toBeEnabled();
  }
  for (const invalid of ['Hong','홍1','홍!','ㅎ','홍'.repeat(101)]) {
    await input.fill(invalid);
    await expect(input).toHaveAttribute('aria-invalid','true');
    await expect(analyze).toBeDisabled();
  }
  await input.fill('홍'+'가'.repeat(99));
  await expect(preview).toHaveText(`홍${'㉠'.repeat(99)}으로 제출됩니다.`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await input.dispatchEvent('compositionstart');
  await input.fill('홍ㄱ');
  await expect(input).toHaveAttribute('aria-invalid','false');
  await expect(preview).toHaveText('홍으로 제출됩니다. (입력 중)');
  await expect(analyze).toBeDisabled();
  await input.fill('홍길동');
  await input.dispatchEvent('compositionend');
  await expect(preview).toHaveText('홍㉠㉢으로 제출됩니다.');
  await analyze.click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  await expect(page.getByRole('dialog')).toBeHidden();
  const submit = page.getByRole('button',{name:'KYWA AI 안전센터로 데이터 전송',exact:true});
  await input.fill('');
  await expect(submit).toBeDisabled();
  await input.fill('홍A');
  await expect(submit).toBeDisabled();
  await input.fill('김하늘별');
  await expect(preview).toHaveText('김㉭㉡㉥으로 제출됩니다.');
  const location = `성명검사-${info.project.name}-${Date.now()}`;
  await page.locator('.evaluation-row').getByLabel('장소',{exact:true}).fill(location);
  await submit.click();
  await expect(page.locator('.progress-dialog [role="status"]')).toContainText('1건을 제출했습니다');
  await expect(input).toHaveValue('');
  await expect(input).toHaveAttribute('aria-invalid','false');
  const analysisRequests = requests.filter(r => new URL(r.url).pathname === '/api/analyses');
  const submissions = requests.filter(r => new URL(r.url).pathname === '/api/assessments' && r.body);
  expect(analysisRequests).toHaveLength(1);
  expect(submissions).toHaveLength(1);
  expect(analysisRequests[0].body).not.toContain('submitter_name');
  expect(JSON.parse(submissions[0].body).submitter_name).toBe('김㉭㉡㉥');
  for (const raw of ['홍길동','김하늘별']) expect(JSON.stringify(requests)).not.toContain(raw);
  const storage = await page.evaluate(() => JSON.stringify({local:{...localStorage},session:{...sessionStorage},url:window.location.href}));
  expect(storage).not.toContain('홍길동'); expect(storage).not.toContain('김하늘별');
  await page.getByRole('button',{name:'개선조치 · 재평가',exact:true}).click();
  await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  const record = page.getByRole('button').filter({has:page.getByRole('heading',{name:location,exact:true})});
  await expect(record.locator('.record-submitter')).toHaveText('제출자 성명: 김㉭㉡㉥');
  await record.click();
  await expect(page.locator('.detail-submitter')).toHaveText('제출자 성명: 김㉭㉡㉥');
  await page.getByLabel('실제 조치내용',{exact:true}).fill('시험용 보수 완료');
  await page.getByRole('button',{name:'AI 재평가하기',exact:true}).click();
  await expect(page.locator('.reassessment')).toBeVisible();
  const reassess = requests.filter(r => r.url.endsWith('/reassess'));
  expect(reassess).toHaveLength(1);
  expect(reassess[0].body).not.toContain('submitter_name');
  expect(reassess[0].body).not.toContain('김㉭㉡㉥');
  await page.getByRole('button',{name:'결과보고서',exact:true}).click();
  await expect(page.locator('tbody tr').filter({hasText:location}).locator('.report-submitter')).toHaveText('김㉭㉡㉥');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath('masked-name-reports.png'),fullPage:true});
});

for (const mode of ['optional','disabled'] as const) {
  test(`name field ${mode} UI`, async ({page}) => {
    await page.route('**/api/bootstrap', async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.organization.submitter_name.mode = mode;
      await route.fulfill({response,json:data});
    });
    await page.goto('/');
    await page.getByLabel('어떤 위험이 있나요?', {exact:false}).fill('시험 설명');
    const input = page.getByLabel('제출자 성명',{exact:true});
    const analyze = page.getByRole('button',{name:'KYWA AI 위험요인 분석 시작',exact:true});
    await expect(analyze).toBeEnabled();
    if (mode === 'disabled') await expect(input).toHaveCount(0);
    else {
      await input.fill('홍A'); await expect(analyze).toBeDisabled();
      await input.fill(''); await expect(analyze).toBeEnabled();
    }
  });
}
