// Compare application-cold reads on already warm hosts, alternating on the same PC/browser.
import {chromium} from '@playwright/test';
import {performance} from 'node:perf_hooks';
const hosts=['https://kywa-safety-pilot-api.onrender.com','https://kywa-safety-pilot.vercel.app'];
const browser=await chromium.launch(), pages=[],times=[[],[]];
try{
  for(const origin of hosts){
    const page=await browser.newPage();
    await page.addInitScript(()=>{
      const fetch0=window.fetch;
      window.fetch=function(input,init){if(typeof input==='string' && input.startsWith('/api/overview?'))input+='&fresh=1&t='+Date.now();return fetch0.call(this,input,init);};
      let start;
      new MutationObserver(()=>{if(document.querySelector('.public-overview'))start??=performance.now();
        if(start!==undefined && window.firstGraph===undefined && document.querySelector('.overview-charts')){
          window.firstGraph=null;requestAnimationFrame(()=>requestAnimationFrame(()=>{window.firstGraph=performance.now()-start;}));
        }
      }).observe(document,{childList:true,subtree:true});
    });
    await page.goto(origin);if(new URL(page.url()).origin!==origin)throw Error('Unexpected origin');
    await page.locator('.overview-charts').waitFor();
    const login=await page.evaluate(async pin=>{const boot=await(await fetch('/api/bootstrap')).json();
      const f=new FormData();f.set('pin',pin);return(await fetch('/api/auth/pin',{method:'POST',headers:{'X-CSRF-Token':boot.csrf},body:f})).status;},process.env.PILOT_PIN);
    if(login!==200)throw Error('Pilot login HTTP '+login);
    pages.push(page);
  }
  for(let i=0;i<21;i++){
    for(const j of (i%2?[1,0]:[0,1])){
      const page=pages[j];await page.goto(hosts[j]+'/?round='+i+'#inspect');
      await page.waitForFunction(()=>typeof window.firstGraph==='number');
      const graph=await page.evaluate(()=>window.firstGraph);
      const t=performance.now();
      await page.getByRole('button',{name:'개선조치 · 재평가',exact:true}).click();
      await page.locator('.record-item').first().waitFor();
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      if(i)times[j].push({list:performance.now()-t,graph});
    }
    console.log('pair',i);await new Promise(r=>setTimeout(r,4500));
  }
  for(const [j,rows] of times.entries())for(const k of ['list','graph']){
    const v=rows.map(x=>Math.round(x[k])).sort((a,b)=>a-b);
    console.log(JSON.stringify({url:hosts[j],cold_ui:k,n:v.length,median_ms:(v[9]+v[10])/2,p95_ms:v[18]}));
  }
}finally{await browser.close();}
