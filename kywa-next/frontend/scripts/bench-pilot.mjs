import { chromium, devices } from '@playwright/test';
import { performance } from 'node:perf_hooks';

const [url, profile = 'desktop'] = process.argv.slice(2);
const allowed = new Set(['kywa-safety-pilot-api.onrender.com', 'kywa-safety-pilot.vercel.app', 'localhost', '127.0.0.1']);
if (!url || !allowed.has(new URL(url).hostname) || !process.env.PILOT_PIN) throw Error('시험 URL과 PILOT_PIN이 필요합니다.');
const browser = await chromium.launch();
const context = await browser.newContext(profile === 'mobile-emulation' ? devices['Pixel 7'] : {});
const page = await context.newPage();
const gets = {overview:0,list:0};
page.on('request',req=>{ const p=new URL(req.url()).pathname; if (p==='/api/overview') gets.overview++; if (p==='/api/assessments' && req.method()==='GET') gets.list++; });
await page.addInitScript(()=>{let start=null; const inspect=()=>{if(start===null && document.querySelector('.public-overview')) start=performance.now();
  if(start!==null && document.querySelector('.overview-charts') && window.pilotFirstGraph===undefined) window.pilotFirstGraph=performance.now()-start;};
  new MutationObserver(inspect).observe(document,{childList:true,subtree:true});});
const samples = {list: [], graph: []};
const spacing = Math.max(6000,Number(process.env.PILOT_INTERVAL_MS)||6000);
const failures={};
page.on('response',r=>{if (new URL(r.url()).pathname.startsWith('/api/')&&r.status()>=400) {const k=r.status()+' '+new URL(r.url()).pathname;failures[k]=(failures[k]||0)+1;}});
async function measure(label, button, target) {
  const start = performance.now();
  await button.click();
  await target.waitFor({state: 'visible'});
  await page.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
  return performance.now() - start;
}
try {
  await page.goto(url);
  if (new URL(page.url()).origin!==new URL(url).origin) throw Error('시험 주소에서 벗어났습니다.');
  await page.locator('.overview-charts').waitFor();
  const login = await page.evaluate(async pin => {
    const boot = await (await fetch('/api/bootstrap')).json();
    const form = new FormData();
    form.set('pin',pin);
    return (await fetch('/api/auth/pin',{method:'POST',headers:{'X-CSRF-Token':boot.csrf},body:form})).status;
  },process.env.PILOT_PIN);
  if (login!==200) throw Error('시험 관리자 로그인 실패 HTTP '+login);
  await page.reload();
  const listButton = page.getByRole('button',{name:'개선조치 · 재평가',exact:true});
  const graphButton = page.getByRole('button',{name:'AI 위험성평가',exact:true});
  const list = page.locator('.record-item').first();
  const graph = page.locator('.overview-charts');
  await graph.waitFor();
  console.log(JSON.stringify({profile,initial_graph_ms:await page.evaluate(()=>window.pilotFirstGraph)}));
  for (let i=0;i<21;i++) {
    const listTime=await measure('list',listButton,list);
    const graphTime=await measure('graph',graphButton,graph);
    if (i===0) console.log(JSON.stringify({first:{list_ms:listTime,graph_ms:graphTime}}));
    else { samples.list.push(listTime);samples.graph.push(graphTime); }
    console.log(JSON.stringify({round:i,list_ms:Math.round(listTime),graph_ms:Math.round(graphTime)}));
    // Finish refreshes from the previous navigation before starting another sample.
    await page.waitForLoadState('networkidle');
    await new Promise(resolve=>setTimeout(resolve,spacing));
  }
  for (const [name,values] of Object.entries(samples)) {
    const sorted=[...values].sort((a,b)=>a-b);
    console.log(JSON.stringify({url,profile,name,n:20,median_ms:(sorted[9]+sorted[10])/2,p95_ms:sorted[18],samples_ms:values}));
  }
  console.log(JSON.stringify({browser_gets:gets}));
} finally { console.log(JSON.stringify({observed_http_errors:failures})); await browser.close(); }
