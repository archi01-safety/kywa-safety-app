import {test,expect} from '@playwright/test';

test('verified law citations have separate public links and reuse the same lookup',async({page})=>{
  test.skip(!!process.env.ORGANIZATION_ID&&process.env.ORGANIZATION_ID!=='kywa');
  let requests=0;
  const text='산업안전보건법 제38조; 산업안전보건기준에 관한 규칙 제4조';
  await page.route('**/api/analyses',async route=>{const response=await route.fetch();const data=await response.json();data.items[0].law=text;await route.fulfill({json:data});});
  await page.route('**/api/law-links?*',async route=>{requests++;await route.fulfill({json:{configured:true,items:[
    {label:'산업안전보건법 제38조',url:'https://www.law.go.kr/법령/산업안전보건법/제38조',verified:true,effective_date:'20261027',message:'공식 원문 확인'},
    {label:'산업안전보건기준에 관한 규칙 제4조',url:'https://www.law.go.kr/법령/산업안전보건기준에관한규칙/제4조',verified:true,effective_date:'20260302',message:'공식 원문 확인'}]}});});
  await page.goto('/');
  await page.getByLabel('제출자 성명',{exact:true}).fill('홍길동');
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill('복도 적치물');
  const analyze=page.getByRole('button',{name:'KYWA AI 위험요인 분석 시작',exact:true});
  await analyze.click();await expect(page.getByRole('dialog')).toBeHidden();
  const links=page.locator('.evaluation-law .law-references a');await expect(links).toHaveCount(2);
  for(const link of await links.all()){
    await expect(link).toContainText('공식 원문 · 시행');
    expect(await link.getAttribute('href')).not.toMatch(/[?&](OC|key|token)=/i);
    await expect(link).toHaveAttribute('target','_blank');
  }
  expect(requests).toBe(1);
  await page.getByRole('button',{name:'다시 분석하기',exact:false}).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(links).toHaveCount(2);expect(requests).toBe(1);
});
