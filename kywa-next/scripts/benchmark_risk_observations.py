"""Opt-in repeatability experiment. Synthetic cases; never an expert accuracy claim."""
import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import Settings
from backend.detailed_risk import resolve
from backend.services import AIService

CASES=[
    ('minor-floor','사무실 바닥의 작은 케이블 걸림 위험 한 건만 평가합니다. 월 단위로 이용하며 위험원과 분리되어 있고 효과적인 안전조치가 확인됩니다. 위험 상태는 안정적이고 확대되지 않습니다. 예상 피해는 경미한 부상이고 피해 범위는 매우 제한적입니다.'),
    ('corridor','복도 바닥 케이블 걸림 위험 한 건만 평가합니다. 일 단위로 이용하며 부주의하면 접촉할 수 있고 일부 안전조치만 확인됩니다. 위험 상태는 안정적이고 확대되지 않습니다. 예상 피해는 응급처치 이상이지만 비휴업 수준이며 피해 범위는 제한적입니다.'),
    ('fall','높이 3m 작업대의 난간 미설치 추락 위험 한 건만 평가합니다. 일 단위로 이용하며 가장자리 위험에 직접 노출되고 조치 없음이 확인됩니다. 위험 상태는 악화되고 있습니다. 예상 피해는 사망 또는 영구 장애이고 피해 범위는 매우 넓습니다.'),
    ('electric','충전부에 손이 닿는 분전반 작업의 감전 위험 한 건만 평가합니다. 상시 반복 작업이며 위험에 직접 노출되고 조치 없음이 확인됩니다. 위험 상황이 반복됩니다. 예상 피해는 사망 또는 영구 장애이고 피해 범위는 매우 넓습니다.'),
]

def key_from_file(path):
    from dotenv import dotenv_values
    if Path(path).suffix=='.env':
        values=dotenv_values(path)
        return values.get('GEMINI_API_KEY',''),values.get('GEMINI_MODEL','')
    # Key formats can change. Select one complete token without printing it.
    keys=set(re.findall(r'[0-9A-Za-z_.-]{25,}',Path(path).read_text(encoding='utf-8-sig')))
    if len(keys)!=1:raise ValueError('비공개 파일의 인증정보 형식을 확인하세요.')
    return keys.pop(),''

def run(key_file,organization,repeats,output):
    key,model=key_from_file(key_file)
    if not key:raise ValueError('시험용 서버 인증정보가 없습니다.')
    cfg=Settings(_env_file=None,app_env='development',organization_id=organization,gemini_api_key=key)
    if model:cfg.gemini_model=model
    ai=AIService(cfg);results=[]
    for case_id,description in CASES:
        attempts=[]
        for number in range(repeats):
            started=time.monotonic()
            facts=ai.observe(cfg.organization.facilities[0],cfg.organization.departments[0] if cfg.organization.departments else '',description)
            _,questions,items=resolve(facts,cfg.organization.policy)
            public=[{k:r[k] for k in ('p','s','score','grade')} for r in items]
            attempts.append({'facts':facts,'questions':questions,'public_scores':public,'seconds':round(time.monotonic()-started,3)})
            print(json.dumps({'case':case_id,'repeat':number+1,'completed':True}),flush=True)
        signatures=Counter(json.dumps(x['public_scores'],ensure_ascii=False,sort_keys=True) for x in attempts)
        results.append({'case':case_id,'description_sha256':hashlib.sha256(description.encode()).hexdigest(),
            'distinct_public_results':len(signatures),'all_facts_resolved':all(not x['questions'] for x in attempts),
            'attempts':attempts})
    summary={'organization':organization,'model':cfg.gemini_model,'cases':len(results),'repeats':repeats,
        'identical_public_scores':sum(r['distinct_public_results']==1 for r in results),
        'all_facts_resolved':all(r['all_facts_resolved'] for r in results),
        'expert_comparison':'not_provided','photo_angle_comparison':'not_tested',
        'activation_authorized':False,'notes':'No result cache used; temperature zero alone does not guarantee identical observations.'}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--key-file',required=True)
    p.add_argument('--organization',default='kywa');p.add_argument('--repeats',type=int,choices=range(2,6),default=3)
    p.add_argument('--output',default='local-data/v11-risk-benchmark.json');a=p.parse_args()
    run(a.key_file,a.organization,a.repeats,a.output)
