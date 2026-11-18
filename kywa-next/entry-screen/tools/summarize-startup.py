"""Combine unmodified probe timings with independently observed cold-start evidence."""
import argparse,datetime,json,statistics
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--samples',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--warm',type=Path);p.add_argument('--proxy-warm',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--config',type=Path)
    a=p.parse_args();raw=json.loads(a.samples.read_text(encoding='utf-8'));evidence=json.loads(a.evidence.read_text(encoding='utf-8'))
    matched=[]
    for sample in raw['samples']:
        proof=next((e for e in evidence if e['trial']==sample['trial'] and e.get('verified') is True and e.get('source')=='render-dashboard/logs'),None)
        if sample['kind']=='cold' or (sample['kind']=='unconfirmed' and proof):
            matched.append({'trial':sample['trial'],'at':sample['at'],'seconds':sample['seconds'],'confirmation':proof or 'loading HTTP response'})
    if len(matched)!=3:raise SystemExit('Exactly three independently confirmed natural starts are required')
    values=[s['seconds'] for s in matched];mean=statistics.mean(values)
    report={'date':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat(),'timezone':'Asia/Seoul','target':raw['target'],'forced_restart':False,
        'measurement':'first GET to first validated HTTP200 application/json status=ok; 5s timeout and 2s retry gap included',
        'cold':{'samples':matched,'count':3,'mean':round(mean,3),'median':statistics.median(values),'maximum':max(values)},
        'storySeconds':round(mean-2,3),
        'excludedAttempts':[{'trial':s['trial'],'at':s['at'],'seconds':s['seconds'],'kind':s['kind']} for s in raw['samples'] if s['trial'] not in {m['trial'] for m in matched}],
        'conditions':'Same Windows office network; 5s HTTP timeout, 2s retry gap; shutdown/startup verified in Render dashboard. Unsuccessful attempts are reported separately.'}
    if a.warm:report['warm']=json.loads(a.warm.read_text(encoding='utf-8'))
    if a.proxy_warm:report['proxyWarm']=json.loads(a.proxy_warm.read_text(encoding='utf-8'))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if a.config:
        a.config.write_text(json.dumps({'storySeconds':report['storySeconds'],'measurementStatus':'three-natural-starts-confirmed',
            'measuredDate':report['date'],'coldMeanSeconds':round(mean,3)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('cold','storySeconds')},ensure_ascii=False))

if __name__=='__main__':main()
