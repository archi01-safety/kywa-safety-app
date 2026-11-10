// Run through scripts/check_pilot_edits.py --ui, using only its disposable row.
import { chromium } from '@playwright/test';
import { performance } from 'node:perf_hooks';
import { createInterface } from 'node:readline';
const [origin,tag]=process.argv.slice(2);
if (!['https://kywa-safety-pilot-api.onrender.com','https://kywa-safety-pilot.vercel.app'].includes(origin) ||
    !/^PILOT-QA-[0-9a-f]{32}$/.test(tag) || !process.env.PILOT_PIN) throw Error('Pilot fixture required');
const browser=await chromium.launch();
try {
  const page=await browser.newPage(), input=createInterface({input:process.stdin});
  await page.goto(origin); if(new URL(page.url()).origin!==origin) throw Error('Unexpected redirect');
  const ok=await page.evaluate(async pin=>{
    const boot=await(await fetch('/api/bootstrap')).json(),form=new FormData();
    form.set('pin',pin);return(await fetch('/api/auth/pin',{method:'POST',headers:{'X-CSRF-Token':boot.csrf},body:form})).ok;
  },process.env.PILOT_PIN);
  if(!ok)throw Error('Pilot login failed');
  await page.reload(); await page.getByRole('button',{name:'개선조치 · 재평가',exact:true}).click();
  await page.locator('.record-item').first().waitFor();await page.waitForLoadState('networkidle');
  const row=page.locator('.record-item').filter({hasText:tag});
  const originalCount=await page.locator('.record-item').count();
  console.log('READY');
  for await(const phase of input) {
    if(!['add','edit','delete'].includes(phase)) throw Error('Invalid phase');
    const start=performance.now();
    await page.getByRole('button',{name:'목록 새로고침',exact:true}).click();
    if(phase==='add') await row.waitFor();
    if(phase==='edit') await row.getByText('수정된 합성 위험상황',{exact:true}).waitFor();
    if(phase==='delete') {
      await row.waitFor({state:'detached'});
      await page.waitForFunction(n=>document.querySelectorAll('.record-item').length===n,originalCount);
    }
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    console.log(JSON.stringify({phase,visible_ms:Math.round(performance.now()-start)}));
    if(phase==='delete')break;
  }
} finally {await browser.close();}
