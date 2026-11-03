import {test,expect} from '@playwright/test';

test('facility and all-facility exports use server names in all three formats',async({page},info)=>{
  test.skip(!!process.env.ORGANIZATION_ID && process.env.ORGANIZATION_ID!=='kywa');
  let filter='';let format='';
  await page.route('**/api/report-jobs',async route=>{
    const body=route.request().postDataJSON();filter=body.facility;format=body.format;
    await route.fulfill({json:{id:'filename-fixture'}});
  });
  await page.route('**/api/report-jobs/filename-fixture',async route=>route.fulfill({json:{state:'complete'}}));
  await page.route('**/api/report-jobs/filename-fixture/download',async route=>route.fulfill({body:'filename fixture',headers:{'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename*=UTF-8''${encodeURIComponent(`${filter||'KYWA'}_위험성평가_20261102.${format}`)}`}}));
  await page.goto('/#reports');await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();await expect(page.getByRole('dialog')).toBeHidden();
  for(const facility of ['우주','']){
    await page.locator('.filter-panel select').first().selectOption(facility);
    for(const [label,ext] of [['Excel 다운로드','xlsx'],['PDF 다운로드','pdf'],['한글 보고서','hwpx']]){
      const pending=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:false}).click();
      const file=await pending;expect(file.suggestedFilename()).toBe(`${facility||'KYWA'}_위험성평가_20261102.${ext}`);
      await expect(page.getByRole('dialog')).toBeHidden();
    }
  }
  await page.screenshot({path:info.outputPath('report-downloads.png'),fullPage:true});
});
