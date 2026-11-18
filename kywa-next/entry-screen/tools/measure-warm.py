"""Ten bounded readiness samples during an explicit test visit; never a scheduler."""
import argparse,datetime,json,statistics,time
from pathlib import Path
import httpx
TARGETS={'direct':'https://kywa-safety.onrender.com/healthz','proxy':'https://kywa-safety-start.netlify.app/__render/ready'}
def main():
    p=argparse.ArgumentParser();p.add_argument('--target',choices=TARGETS,default='direct');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    samples=[]
    with httpx.Client(timeout=5,follow_redirects=False,headers={'Accept':'application/json','Cache-Control':'no-cache','User-Agent':'KYWA-Entry-Bounded-Measurement/1.0'}) as client:
        for i in range(10):
            client.cookies.clear();start=time.perf_counter()
            try:
                r=client.get(TARGETS[a.target],params={'_entry_warm':str(time.time_ns())})
                ready=r.status_code==200 and 'application/json' in r.headers.get('content-type','') and r.json()=={'status':'ok'}
                samples.append({'trial':i+1,'seconds':round(time.perf_counter()-start,3),'status':r.status_code,'ready':ready,'cache_control':r.headers.get('cache-control','')})
            except (httpx.HTTPError,ValueError):samples.append({'trial':i+1,'seconds':round(time.perf_counter()-start,3),'ready':False})
    values=[s['seconds'] for s in samples if s['ready']]
    result={'target':TARGETS[a.target],'at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'),
        'samples':samples,'count':len(values),'mean':round(statistics.mean(values),3) if values else None,'median':statistics.median(values) if values else None,
        'maximum':max(values) if values else None,'within650ms':sum(v<=.65 for v in values),'ai_google_calls':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
    if len(values)!=10:raise SystemExit('Not all ten readiness checks succeeded')
if __name__=='__main__':main()
