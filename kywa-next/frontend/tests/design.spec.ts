import { test, expect } from '@playwright/test';

const institution = process.env.ORGANIZATION_ID || 'kywa';
test('design scope, responsive screens and color-only partner geometry', async ({page}, info) => {
  test.skip(institution === 'example', 'Eight production institution themes only');
  await page.goto('/');
  await expect(page.locator('.eyebrow').first()).toContainText('SMART SAFETY');
  const premium = institution === 'kywa';
  await expect(page.locator('html')).toHaveAttribute('data-design', premium ? 'premium' : 'standard');
  await expect(page.locator('.premium-ribbons')).toHaveCount(premium ? 1 : 0);
  if (!premium) {
    await expect(page.locator('.institution-header')).toHaveCSS('background-color','rgb(255, 255, 255)');
    // Changing brand tokens must never change standard institution dimensions or text.
    const geometry = () => page.locator('.institution-header,.sidebar,.panel,input,textarea,select,button').evaluateAll(elements => elements.map(el => {
      const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
      return [r.x,r.y,r.width,r.height,s.fontSize,s.padding,s.borderRadius,el.textContent];
    }));
    const before = await geometry();
    const values = await page.evaluate(() => {
      const root=document.documentElement; const saved=root.getAttribute('style');
      for(const key of ['--brand-original','--brand-button','--brand-hover','--brand-dark-text','--brand-light-text','--brand-secondary-original','--brand-secondary-dark-text','--brand-secondary-light-text']) root.style.setProperty(key,'#64748B');
      return saved;
    });
    expect(await geometry()).toEqual(before);
    await page.evaluate(saved=>document.documentElement.setAttribute('style',saved || ''),values);
  }
  for(const theme of ['dark','light']) {
    if(theme==='light') await page.getByRole('button',{name:'밝은 테마',exact:true}).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath(`${institution}-${theme}-inspect.png`),fullPage:true});
    await page.screenshot({path:info.outputPath(`${institution}-${theme}-viewport.png`)});
  }
  await page.getByRole('button',{name:'어두운 테마',exact:true}).click();
  await page.getByLabel('제출자 성명',{exact:true}).fill('홍길동');
  await page.getByLabel('어떤 위험이 있나요?',{exact:false}).fill('시연용 테라스 난간 흔들림');
  await page.locator('.analyze-button').click();
  await expect(page.locator('.evaluation-row')).toHaveCount(1);
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.locator('.submit-bar .primary').click();
  await expect(page.locator('.progress-dialog [role="status"]')).toContainText('1건을 제출했습니다');
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button',{name:'개선조치 · 재평가',exact:true}).click();
  await page.getByRole('button',{name:'관리자로 체험하기',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.locator('.record-item').first().click();
  for (const tab of ['actions','reports']) {
    if(tab==='reports') await page.getByRole('button',{name:'결과보고서',exact:true}).click();
    for(const theme of ['dark','light']) {
      if(theme==='light') await page.getByRole('button',{name:'밝은 테마',exact:true}).click();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:info.outputPath(`${institution}-${theme}-${tab}.png`),fullPage:true});
    }
    await page.getByRole('button',{name:'어두운 테마',exact:true}).click();
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  if(premium) {
    const transitions=await page.locator('.primary').first().evaluate(el=>getComputedStyle(el).transitionDuration);
    expect(transitions).toBe('0s');
  }
});
