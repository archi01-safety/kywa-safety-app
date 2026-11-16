"""Synthetic policy anchors and held-out scenarios, independently specified target p/s."""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.organization import load_organization
from backend.detailed_risk import FACTS, Observation, resolve
from backend.risk_profiles import load_profile

ORGS=('kywa','ayf','fowi','khidi','knps','knf','kohi','cayf')
SCENARIOS={
 '시설 안전':('문손잡이 표면의 거친 마감으로 손이 긁힐 위험','건물 옥상 가장자리 난간 미설치로 추락 위험'),
 '화재 안전':('소화기 위치 표지의 작은 훼손','가연성 증기가 축적된 곳에 점화원이 있어 화재와 폭발 위험'),
 '재난 안전':('안전구역의 가벼운 안내판 고정 상태 확인','집중호우 중 토사와 축대가 무너져 매몰될 위험'),
 '작업 안전':('가벼운 상자의 모서리에 손이 긁힐 위험','높이 3m 작업대 가장자리에 안전대 없이 노출되어 추락 위험'),
 '작업 특성':('키보드 작업 중 손목의 일시적 불편','과도한 중량물을 반복 운반하다 압착되는 위험'),
 '기계(설비)적 요인':('정지한 설비 외함 모서리에 손이 긁힐 위험','가동 중인 회전체에 방호덮개가 없어 끼임 위험'),
 '전기적 요인':('전원이 분리된 장비 외함 마감에 긁힐 위험','활선 상태 분전반 충전부에 손이 직접 닿아 감전 위험'),
 '보건 및 위생관리':('환기되는 사무실의 일시적인 불편','산소결핍이 확인된 밀폐공간에 보호 없이 들어가는 질식 위험'),
 '화학물질 관리':('저자극 세정제 용기 외면에 접촉하는 위험','급성 독성물질에 고농도로 노출되는 위험'),
 '작업 환경':('잠깐 이용하는 장소의 일시적 눈부심','밀폐된 고온 공간에서 보호 없이 반복 작업하는 중대 온열질환 위험'),
 '보행 안전':('바닥의 작은 케이블에 발이 걸리는 위험','차량과 보행자가 분리되지 않은 통로에서 충돌 위험'),
 '활동 안전':('지면의 가벼운 활동도구에 부딪히는 위험','보호장치가 없는 고소 활동 시설에서 추락 위험')}
ANCHORS=[
 ({'exposure':'rare','contact':'isolated','controls':'effective','condition':'stable','consequence':'minor','extent':'very_limited'},(1,1)),
 ({'exposure':'daily','contact':'unlikely','controls':'partial','condition':'stable','consequence':'first_aid','extent':'limited'},(2,2)),
 ({'exposure':'daily','contact':'possible','controls':'ineffective','condition':'degrading','consequence':'lost_time','extent':'moderate'},(4,3)),
 ({'exposure':'continuous','contact':'direct','controls':'none','condition':'repeated','consequence':'fatal','extent':'critical'},(5,4))]


def observation(category,facts,scenario):
    return Observation(category=category,location='합성 시험 현장',scenario=scenario,solution='위험원 제거와 접근 통제',law='',**facts).model_dump()


def describe(item):
    labels={f:{k:t for k,t,_ in options} for f,(_,options) in FACTS.items()}
    return ('합성 검증 사례이며 다음 위험 한 건만 평가합니다. 분류: '+item['category']+'. 위험상황: '+item['scenario']+'. 장소: '+item['location']+'. '
        +' '.join(f'{field}: {labels[field][item[field]]}.' for field in FACTS)
        +' 이 사례에 명시된 조건과 예상 피해를 그대로 관찰하고, 다른 위험을 추가하지 마세요.')


def cases_for(org_id):
    org=load_organization(org_id);cases=[]
    def add(key,item,pair,split,extra=''):
        expected=org.policy.risk(*pair)
        cases.append({'id':key,'split':split,'observation':item,'description':describe(item)+extra,
            'source':{'policy':org.policy.version,'p_description':next(x.description for x in org.policy.p_levels if x.value==pair[0]),
                      's_description':next(x.description for x in org.policy.s_levels if x.value==pair[1])},
            'expected':{k:expected[k] for k in ('p','s','score','grade')}})
    for index,category in enumerate(org.categories):
        for level,(facts,pair) in enumerate(ANCHORS):
            scenario=SCENARIOS[category][1 if level==3 else 0]
            if level in (1,2):scenario+='; 예상 피해와 노출 조건은 아래 명시된 사실을 기준으로 함'
            add(f'category-{index+1:02}-{level+1}',observation(category,facts,scenario),pair,'holdout' if level==3 else 'development')
    if org_id=='fowi':
        for ratio,p in [(9,1),(10,2),(70,4),(100,5)]:
            item=observation('화학물질 관리',ANCHORS[1][0],'측정된 유해물질 노출수준 확인')
            item.update(hazard='chemical',exposure_percent=ratio)
            add(f'measured-ratio-{ratio}',item,(p,2),'holdout',f' 측정 노출수준은 법적기준의 {ratio}%입니다.')
        for hours,p in [(3,3),(4,4),(8,5)]:
            item=observation('작업 특성',ANCHORS[0][0],'반복 작업의 작업시간 확인')
            item.update(hazard='ergonomic',daily_hours=hours)
            add(f'measured-hours-{hours}',item,(p,1),'holdout',f' 하루 {hours}시간 작업합니다.')
        for noise,s in [(80,2),(85,3),(90,4)]:
            item=observation('작업 환경',ANCHORS[0][0],'측정된 작업장 소음 확인')
            item.update(hazard='noise',noise_db=noise)
            add(f'measured-noise-{noise}',item,(1,s),'holdout',f' 측정 소음은 {noise}dB입니다.')
        for consequence,s in [('minor',1),('first_aid',2)]:
            facts={**ANCHORS[1][0],'exposure':'continuous','contact':'possible','controls':'none','consequence':consequence}
            add('minor-cap-'+consequence,observation('시설 안전',facts,'높이차나 전기 위험이 없는 경미한 마감 손상'),(4 if s==1 else 2,s),'holdout')
    else:
        boundaries=[('monthly','unlikely','effective','stable',1),('daily','unlikely','effective','stable',2),
            ('daily','possible','effective','stable',2),('continuous','possible','effective','stable',3),
            ('daily','possible','partial','degrading',3),('daily','possible','ineffective','degrading',4),
            ('continuous','direct','partial','degrading',4),('continuous','direct','partial','repeated',5)]
        for index,(exposure,contact,controls,condition,p) in enumerate(boundaries):
            facts={**ANCHORS[2][0],**dict(exposure=exposure,contact=contact,controls=controls,condition=condition)}
            add(f'likelihood-boundary-{index+1}',observation('작업 안전',facts,'작업 도구와 접촉하여 휴업 부상이 예상되는 위험'),(p,3),'holdout')
        for index,(consequence,extent,s) in enumerate([('minor','critical',1),('first_aid','very_limited',2),('lost_time','critical',3),('fatal','very_limited',4)]):
            facts={**ANCHORS[3][0],'consequence':consequence,'extent':extent}
            add(f'severity-boundary-{index+1}',observation('작업 안전',facts,'주어진 피해 정도에 해당하는 작업 중 사고 위험'),(5,s),'holdout')
    assert len(cases)==60 and sum(c['split']=='development' for c in cases)==36
    return cases


def export(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);summaries=[]
    for org_id in ORGS:
        org=load_organization(org_id);cases=cases_for(org_id)
        for c in cases:
            _,_,items=resolve([c['observation']],org.policy,optional=True,evidence_text=c['description'])
            actual={k:items[0][k] for k in c['expected']}
            if actual!=c['expected']:raise AssertionError((org_id,c['id'],actual,c['expected']))
        mapping=[{'likelihood':l,'severity':s,'internal_product':l*s,
            **{k:v for k,v in org.policy.risk((l+2)//3,(s+4)//5).items() if k in ('p','s','score','grade')}}
            for l in range(1,16) for s in range(1,21)]
        (folder/(org_id+'.json')).write_text(json.dumps({'organization':org_id,'name':org.name,'short_name':org.short_name,
            'fact_options':{field:[{'key':k,'label':t,'weight':w} for k,t,w in options] for field,(_,options) in FACTS.items()},'profile':load_profile(org.policy.version),
            'cases':cases,'mapping':mapping},ensure_ascii=False,indent=2),encoding='utf-8')
        summaries.append({'organization':org_id,'cases':len(cases),'development':36,'holdout':24,'mapping_pairs':len(mapping),'passed':True})
    (folder/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='local-data/v13/backdata');a=p.parse_args();export(a.output)
