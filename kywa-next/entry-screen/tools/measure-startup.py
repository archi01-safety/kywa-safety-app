"""Bounded, manual cold-start measurement. No AI/Google calls or keep-alive job."""
import argparse,datetime,json,os,statistics,time
from pathlib import Path
import httpx

URL='https://kywa-safety.onrender.com/healthz'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=3)
    parser.add_argument('--cooldown',type=int,default=970)
    parser.add_argument('--evidence',type=Path,help='Optional manually verified Render log evidence JSON')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    results=[];state={'target':URL,'ai_google_calls':False,'forced_restart':False,'samples':results}
    def save(**updates):
        state.update(updates);args.output.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds')
    def reconcile():
        if not args.evidence or not args.evidence.exists():return
        evidence=json.loads(args.evidence.read_text(encoding='utf-8'))
        verified={r['trial'] for r in evidence if r.get('source')=='render-dashboard/logs' and r.get('verified') is True}
        for result in results:
            if result['kind']=='unconfirmed' and result['trial'] in verified:
                result['kind']='cold';result['confirmation']='Render shutdown/startup logs independently verified'
    with httpx.Client(timeout=5,follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 KYWA-Entry-Measurement/1.0','Cache-Control':'no-cache'}) as client:
        trial=0
        while sum(r['kind']=='cold' for r in results)<args.samples and trial<args.samples+3:
            trial+=1;start=time.monotonic();probes=[];ready=False
            save(phase='probing',trial=trial,started_at=now(),deadline_seconds=120)
            while time.monotonic()-start<120:
                pstart=time.monotonic()
                try:
                    r=client.get(URL,params={'_entry_probe':str(time.time_ns())})
                    content=r.headers.get('content-type','')
                    is_json='application/json' in content
                    ready=r.status_code==200 and is_json and r.json()=={'status':'ok'}
                    title=''
                    if not is_json:
                        import re
                        found=re.search(r'<title[^>]*>(.*?)</title>',r.text,re.I|re.S)
                        title=found.group(1).strip()[:100] if found else ''
                    probes.append({'status':r.status_code,'type':content,'title':title,'ready':ready,'elapsed':round(time.monotonic()-start,3)})
                except (httpx.HTTPError,ValueError):
                    probes.append({'status':'timeout_or_network','ready':False,'elapsed':round(time.monotonic()-start,3)})
                if ready:break
                save(last_probe=probes[-1]);time.sleep(2)
            elapsed=time.monotonic()-start
            loading=any(p.get('status')==503 or 'starting' in p.get('title','').lower() or 'loading' in p.get('title','').lower() for p in probes)
            kind='cold' if ready and loading and elapsed>=5 else 'warm' if ready and len(probes)==1 else 'unconfirmed' if ready else 'failed'
            result={'trial':trial,'at':now(),'kind':kind,'seconds':round(elapsed,3),'loading_response_observed':loading,'probes':probes}
            results.append(result);save(phase='sample_complete',last_probe=None)
            reconcile();save()
            print(json.dumps({k:v for k,v in result.items() if k!='probes'}),flush=True)
            if sum(r['kind']=='cold' for r in results)>=args.samples:break
            until=time.monotonic()+args.cooldown
            save(phase='natural_idle_wait',next_probe_at=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=args.cooldown)).isoformat(),cooldown_seconds=args.cooldown)
            while time.monotonic()<until:
                time.sleep(min(30,max(.1,until-time.monotonic())));reconcile();save()
                if sum(r['kind']=='cold' for r in results)>=args.samples:break
    cold=[r['seconds'] for r in results if r['kind']=='cold']
    summary={'count':len(cold),'complete':len(cold)>=args.samples}
    if cold:summary.update(mean=round(statistics.mean(cold),3),median=round(statistics.median(cold),3),maximum=max(cold),story_seconds=round(max(1,statistics.mean(cold)-2),3))
    save(phase='complete' if summary['complete'] else 'insufficient_samples',summary=summary)
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
