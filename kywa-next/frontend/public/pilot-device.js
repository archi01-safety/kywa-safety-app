// Opt-in, same-origin device timings. No names, cookies, PINs, or results are collected.
(() => {
  if (document.getElementById('pilot-timing') || !['kywa-safety-pilot-api.onrender.com','kywa-safety-pilot.vercel.app'].includes(location.hostname)) return;
  const pane=document.createElement('aside');pane.id='pilot-timing';
  pane.style.cssText='position:fixed;z-index:999;bottom:4px;right:4px;max-width:min(92vw,32rem);background:#fff;color:#172436;border:1px solid #475467;padding:.55rem;border-radius:.5rem;font:14px/1.4 system-ui';
  const button=document.createElement('button'),out=document.createElement('output');
  out.style.cssText='white-space:pre-wrap;display:block;user-select:text';
  out.textContent='시험 관리자 로그인 후 시작하세요. 다른 탭으로 이동하면 측정을 중지합니다.';
  button.type='button';button.textContent='실기기 측정 시작';pane.append(button,out);document.body.append(pane);
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));let run=false;
  const guard=()=>{if(!run || document.hidden || !pane.isConnected)throw Error('중지됨. 화면을 켜둔 채 다시 시작하세요.');};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)run=false;});
  async function show(name,selector){
    guard();const menu=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===name && b.offsetWidth);
    if(!menu)throw Error('메뉴를 찾을 수 없습니다.');
    const t=performance.now();menu.click();
    while(!document.querySelector(selector)){guard();if(performance.now()-t>45000)throw Error('자료 표시를 확인하지 못했습니다.');await sleep(16);}
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));guard();return Math.round(performance.now()-t);
  }
  button.onclick=async()=>{
    if(run){run=false;button.disabled=true;return;}
    button.disabled=true;
    try {
      if(!(await (await fetch('/api/auth/session',{cache:'no-store'})).json()).active)throw Error('개선조치 메뉴에서 관리자 로그인 후 시작하세요.');
      run=true;button.disabled=false;button.textContent='측정 중지';
      const list=[],graph=[];let first;
      await show('AI 위험성평가','.overview-charts');
      for(let i=0;i<=20;i++){
        const l=await show('개선조치 · 재평가','.record-item'), g=await show('AI 위험성평가','.overview-charts');
        if(i){list.push(l);graph.push(g);}else first={list_ms:l,graph_ms:g};
        out.textContent='측정 '+i+'/20 · 목록 '+l+'ms · 그래프 '+g+'ms';
        if(i<20){for(let j=0;j<12;j++){await sleep(1000);guard();}}
      }
      const stats=v=>{v.sort((a,b)=>a-b);return {median_ms:(v[9]+v[10])/2,p95_ms:v[18]};};
      out.textContent=JSON.stringify({host:location.hostname,rounds:20,first,list:stats(list),graph:stats(graph)},null,2);
    }catch(e){out.textContent=e.message;}finally{run=false;button.disabled=false;button.textContent='실기기 측정 시작';}
  };
})();
