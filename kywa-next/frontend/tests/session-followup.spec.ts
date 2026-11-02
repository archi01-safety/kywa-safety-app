import {test,expect} from '@playwright/test';

test('KYWA session countdown extends explicitly and preserves selected work after expiration',async({page},info)=>{
  test.skip(!!process.env.ORGANIZATION_ID && process.env.ORGANIZATION_ID!=='kywa');
  let remaining=45,expired=false,extensions=0;
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();const data=await response.json();
    if(data.user){data.auth_session={active:!expired,server_time:1000,expires_at:1000+remaining,remaining_seconds:remaining};if(expired)data.user=null;}
    await route.fulfill({response,json:data});
  });
  await page.route('**/api/auth/extend',async route=>{
    extensions++;remaining=3600;
    expect(route.request().headers()['x-csrf-token']).toBeTruthy();
    await route.fulfill({json:{active:true,server_time:1000,expires_at:4600,remaining_seconds:3600}});
  });
  await page.clock.install();
  await page.goto('/');
  await page.getByLabel('제출자 성명',{exact:true}).fill('홍길동');
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill(`로그인 연장 검증 ${info.project.name}`);
  await page.getByRole('button',{name:'KYWA AI 위험요인 분석 시작',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.locator('.evaluation-row').first().getByLabel('장소',{exact:true}).fill(`로그인 연장 검증 ${info.project.name}`);
  const send=page.getByRole('button',{name:'KYWA AI 안전센터로 데이터 전송',exact:true});
  const widths=await send.evaluate(el=>({button:el.getBoundingClientRect().width,box:el.closest('.submit-bar')!.getBoundingClientRect().width}));
  expect(widths.button/widths.box).toBeGreaterThanOrEqual(info.project.name==='mobile'?.85:.49);
  await expect(page.getByText('데이터 전송 시 안전센터 DB에 저장되며, 담당자의 검토가 진행됩니다.',{exact:true})).toBeVisible();
  await send.click();await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button',{name:'개선조치 · 재평가',exact:true}).click();
  await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  await expect(page.getByLabel('로그인 남은 시간',{exact:true})).toBeVisible();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button').filter({has:page.getByRole('heading',{name:`로그인 연장 검증 ${info.project.name}`,exact:true})}).click();
  await page.getByLabel('실제 조치내용',{exact:true}).fill('저장하지 않은 조치 초안');
  await page.getByRole('button',{name:'연장',exact:true}).click();
  await expect(page.getByLabel('로그인 남은 시간',{exact:true})).toContainText(/59:|60:00/);
  expect(extensions).toBe(1);
  await expect(page.getByRole('dialog')).toBeHidden();
  // Fast-forward only the browser clock: the server endpoint is independently tested in Python.
  expired=true;await page.clock.fastForward(3_601_000);
  await expect(page.getByText('로그인 만료',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'담당자 로그인',exact:true})).toBeVisible();
  expired=false;remaining=3600;
  await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  await expect(page.getByLabel('실제 조치내용',{exact:true})).toHaveValue('저장하지 않은 조치 초안');
  expect(extensions).toBe(1);
});
