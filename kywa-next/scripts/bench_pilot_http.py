"""Alternate the two warm deployed read paths, bypassing public aggregate caches."""
import os
import statistics
import time
import requests
from uuid import uuid4

ORIGINS = ['https://kywa-safety-pilot-api.onrender.com','https://kywa-safety-pilot.vercel.app']


def main():
    sessions={}
    for origin in ORIGINS:
        s=requests.Session()
        r=s.get(origin+'/api/bootstrap',timeout=30,allow_redirects=False); r.raise_for_status()
        b=r.json(); assert b['organization']['id']=='kywa' and b['auth_mode']=='pin'
        s.headers.update({'Origin':origin,'X-CSRF-Token':b['csrf']})
        r=s.post(origin+'/api/auth/pin',data={'pin':os.environ['PILOT_PIN']},timeout=30,allow_redirects=False)
        assert r.status_code==200
        sessions[origin]=s
    samples={(o,k):[] for o in ORIGINS for k in ('public','admin')}
    for i in range(21):
        batch={}
        for o in (ORIGINS if i%2==0 else ORIGINS[::-1]):
            for k in ('public','admin'):
                path='/api/overview?year=2026&fresh=1&t='+uuid4().hex if k=='public' else '/api/assessments'
                t=time.perf_counter();r=sessions[o].get(o+path,allow_redirects=False,timeout=60)
                duration=round((time.perf_counter()-t)*1000,1)
                assert r.status_code==200,(o,k,r.status_code)
                result=r.json()
                if k=='public': assert result['total']==150 and result['completed']==50
                else: assert len(result['items'])==150 and 'no-store' in r.headers.get('Cache-Control','')
                if k in batch: assert batch[k]==result
                else: batch[k]=result
                if i: samples[o,k].append(duration)
        print('round',i,flush=True)
        time.sleep(4)
    for (o,k),v in samples.items():
        print(o,k,len(v),'median_ms',statistics.median(v),'p95_ms',sorted(v)[18],flush=True)


if __name__=='__main__':main()
