// Run on the isolated public test app. Files are synthetic, supplied on the command line.
import { chromium } from '@playwright/test';
import { stat } from 'node:fs/promises';
const [origin, jpeg, heic] = process.argv.slice(2);
if (!['https://kywa-safety-pilot.vercel.app','https://kywa-safety-pilot-api.onrender.com'].includes(origin)) throw Error('Pilot origin required');
const b=await chromium.launch();
try {
  const page=await b.newPage();
  await page.addInitScript(()=>{
    const send=window.fetch;
    window.fetch=function(input,init){
      if (String(input).endsWith('/api/photos/prepare') && init?.body instanceof FormData) {
        window.pilotUploadBytes=init.body.get('photo')?.size;
      }
      return send.call(this,input,init);
    };
  });
  await page.goto(origin);
  for (const [type,path] of [['jpeg',jpeg],['heic',heic]]) {
    const bytes=(await stat(path)).size;
    const result=page.waitForResponse(r=>r.url()===origin+'/api/photos/prepare' && r.request().method()==='POST',{timeout:120000});
    await page.getByLabel('현장 사진 선택',{exact:true}).setInputFiles(path);
    const response=await result;
    const requestBytes=await page.evaluate(()=>window.pilotUploadBytes);
    console.log(JSON.stringify({type,original:bytes,uploaded_file_bytes:requestBytes,status:response.status()}));
    if(response.status()!==200 || !requestBytes || type==='jpeg' && requestBytes>3_000_000) throw Error(type+' upload failed');
    const preview=page.getByAltText('분석 전 사진 미리보기');
    await preview.waitFor();
    await preview.evaluate(async i=>{await i.decode(); if(Math.max(i.naturalWidth,i.naturalHeight)>1600) throw Error('Preview size');});
    if(type==='jpeg') await page.getByRole('button',{name:'사진 제거'}).click();
  }
} finally {await b.close();}
