import {test,expect} from '@playwright/test';

test('sheet issues are isolated, current policy confirmation clears report block',async({page},info)=>{
  test.skip(!!process.env.ORGANIZATION_ID && process.env.ORGANIZATION_ID!=='kywa');
  let issue=true,confirmed=0;
  await page.route('**/api/assessments?*',async route=>{
    const response=await route.fetch();const data=await response.json();
    data.issues=issue?[{id:'sheet-fixture',row:24,revision:3,code:'policy_unknown',messages:['최초 평가 기준을 확인하고 현재 KYWA 기준을 적용하세요.'],can_confirm_policy:true,facility:'중앙'}]:[];
    await route.fulfill({response,json:data});
  });
  await page.route('**/api/assessments/sheet-fixture/policy',async route=>{
    const body=route.request().postDataJSON();expect(body.revision).toBe(3);expect(body.request_id).toBeTruthy();
    expect(route.request().headers()['x-csrf-token']).toBeTruthy();issue=false;confirmed++;
    await route.fulfill({json:{ok:true}});
  });
  await page.goto('/#reports');await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  const panel=page.getByRole('region',{name:'시트 확인 필요'});
  await expect(panel).toBeVisible();await expect(page.getByRole('button',{name:'PDF 다운로드',exact:false})).toBeDisabled();
  await page.screenshot({path:info.outputPath('sheet-issues.png'),fullPage:true});
  await page.getByRole('button',{name:'현재 KYWA 기준 적용',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeHidden();await expect(panel).toBeHidden();
  expect(confirmed).toBe(1);await expect(page.getByRole('button',{name:'PDF 다운로드',exact:false})).toBeEnabled();
});

test('sheet revision refresh retains action draft and requests renewed assessment',async({page})=>{
  test.skip(!!process.env.ORGANIZATION_ID && process.env.ORGANIZATION_ID!=='kywa');
  let changed=false;
  await page.route('**/api/assessments?*',async route=>{
    const response=await route.fetch();const data=await response.json();
    if(changed){data.items=data.items.map((r:any)=>({...r,revision:r.revision+1,before:{...r.before,scenario:'시트에서 수정된 위험상황'}}));}
    await route.fulfill({response,json:data});
  });
  await page.goto('/#actions');await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeHidden();await page.locator('.record-item').filter({hasText:'접수'}).first().click();
  await page.getByLabel('실제 조치내용',{exact:true}).fill('작성 중인 조치 초안 보존');
  changed=true;await page.getByRole('button',{name:'목록 새로고침',exact:true}).click();
  await expect(page.getByLabel('실제 조치내용',{exact:true})).toHaveValue('작성 중인 조치 초안 보존');
  await expect(page.getByText('시트 또는 앱에서 평가가 변경되었습니다. 작성한 조치내용과 사진은 유지됩니다. 변경 내용을 확인하고 다시 재평가해 주세요.',{exact:true})).toBeVisible();
});
