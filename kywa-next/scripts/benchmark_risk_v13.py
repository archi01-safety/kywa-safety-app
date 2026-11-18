"""Independent, uncached model repeats against synthetic, published-policy anchors."""
import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import Settings
from backend.services import AIService
from backend.detailed_risk import resolve
from backend.risk_profiles import profile_version
from scripts.risk_backdata import ORGS,cases_for
from scripts.benchmark_risk_observations import key_from_file


def run_org(org_id,key,model,output):
    cfg=Settings(_env_file=None,app_env='development',organization_id=org_id,gemini_api_key=key)
    if model:cfg.gemini_model=model
    ai=AIService(cfg);all_cases=cases_for(org_id)
    selected=[all_cases[i*4+i%4] for i in range(12)]
    if org_id=='fowi':selected[-3:]=[next(c for c in all_cases if c['id']==key) for key in ('measured-ratio-70','measured-hours-8','measured-noise-90')]
    results=[]
    for case in selected:
        attempts=[]
        for repeat in range(3):
            started=time.monotonic()
            try:
                observations=ai.observe(cfg.organization.facilities[0],cfg.organization.departments[0] if cfg.organization.department_enabled else '',case['description'])
                _,questions,items=resolve(observations,cfg.organization.policy,optional=True,evidence_text=case['description'])
                pairs=[(r['p'],r['s']) for r in items]
                expected=[(case['expected']['p'],case['expected']['s'])]
                attempts.append({'observations':observations,'pairs':pairs,'expected_match':pairs==expected,
                    'seconds':round(time.monotonic()-started,3),'questions':len(questions)})
            except Exception as exc:
                attempts.append({'error_type':type(exc).__name__,'pairs':[],'expected_match':False,'seconds':round(time.monotonic()-started,3)})
        signatures=Counter(json.dumps(a['pairs']) for a in attempts)
        results.append({'case':case['id'],'expected':case['expected'],'attempts':attempts,
            'identical':len(signatures)==1 and all(a['pairs'] for a in attempts),
            'critical_underestimate':case['expected']['s']==4 and any(not a['pairs'] or any(p[1]<4 for p in a['pairs']) for a in attempts)})
        Path(output).mkdir(parents=True,exist_ok=True)
        (Path(output)/(org_id+'.json')).write_text(json.dumps({'organization':org_id,'profile':profile_version(cfg.organization.policy),'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'organization':org_id,'case':len(results),'identical':results[-1]['identical']}),flush=True)
    rate=sum(r['identical'] for r in results)/len(results)
    summary={'organization':org_id,'model':cfg.gemini_model,'profile':profile_version(cfg.organization.policy),
        'cases':len(results),'repeats':3,'identical_pair_rate':rate,'expected_matches':sum(a['expected_match'] for r in results for a in r['attempts']),
        'critical_underestimates':sum(r['critical_underestimate'] for r in results),'passed':rate>=.95 and not any(r['critical_underestimate'] for r in results) and all(a['expected_match'] for r in results for a in r['attempts']),
        'expert_accuracy_validated':False,'cache_used':False}
    (Path(output)/(org_id+'.json')).write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--key-file',required=True);p.add_argument('--output',default='local-data/v13/model-benchmark');p.add_argument('--organization',choices=ORGS);p.add_argument('--workers',type=int,choices=(1,2,4),default=2);a=p.parse_args()
    key,model=key_from_file(a.key_file)
    summaries=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        tasks=[pool.submit(run_org,org,key,model,a.output) for org in ((a.organization,) if a.organization else ORGS)]
        for task in as_completed(tasks):
            summaries.append(task.result())
            (Path(a.output)/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries),flush=True)
