import copy
import io
import json
import uuid
from types import SimpleNamespace
from urllib.parse import unquote

import httpx
import pytest
from PIL import Image

from backend.config import Settings
from backend.detailed_risk import Observation, FactAnswer, calculate, resolve
from backend.law_links import LawLinks, verified_records
from backend.organization import load_organization
from backend.risk_profiles import load_profile
from backend.tests.test_photo_workflow_v11 import connect, facts, submit_body
from scripts.risk_backdata import ORGS, cases_for


def law_service(duplicate=False, deleted=False, fail=False):
    calls=[]
    def article(number,title,body='조문 내용'):
        return f'<조문단위><조문번호>{number}</조문번호><조문여부>조문</조문여부><조문제목>{title}</조문제목><조문내용>{body}</조문내용><항><항번호>①</항번호><호><호번호>1.</호번호><호내용>호 내용</호내용></호></항></조문단위>'
    articles={37:article(37,'안전보건표지의 설치ㆍ부착','삭제' if deleted else '표지 설치'),38:article(38,'안전조치'),39:article(39,'보건조치')}
    if duplicate:articles[40]=article(40,'안전조치')
    def get(url,**kwargs):
        calls.append(kwargs['params'])
        if fail:raise httpx.ReadTimeout('synthetic timeout')
        if 'lawSearch' in url:
            xml='<LawSearch><law><법령명한글>산업안전보건법</법령명한글><법령일련번호>12345</법령일련번호><현행연혁코드>현행</현행연혁코드><시행일자>20260101</시행일자><공포번호>00100</공포번호><공포일자>20251201</공포일자></law></LawSearch>'
        else:
            jo=kwargs['params'].get('JO')
            content=articles.get(int(jo[:4]),'') if jo else ''.join(articles.values())
            xml='<법령><기본정보><법령명_한글>산업안전보건법</법령명_한글></기본정보><조문>'+content+'</조문></법령>'
        return httpx.Response(200,content=xml.encode(),request=httpx.Request('GET',url))
    return LawLinks('private-test-only',get),calls


def test_unique_title_changes_text_and_link_without_public_correction_marker():
    service,calls=law_service()
    result=service.resolve_text('산업안전보건법 제37조(안전조치); 산업안전보건법 제39조(보건조치)')
    assert result['text']=='산업안전보건법 제38조(안전조치); 산업안전보건법 제39조(보건조치)'
    assert len(result['items'])==2 and all(r['verified'] for r in result['items'])
    assert '제38조' in unquote(result['items'][0]['url'])
    assert result['_internal_law']['changes']
    assert all(not any(k.startswith('_') or 'correct' in k for k in ref) for ref in result['items'])
    before=len(calls);service.resolve_text('산업안전보건법 제37조(안전조치)')
    assert len(calls)==before  # Full title index and citation are reused.


@pytest.mark.parametrize('text,duplicate,deleted',[
    ('산업안전보건법 제37조(안전조치)',True,False),
    ('산업안전보건법 제37조(안전조치)',False,True),
    ('산업안전보건법 제9999조(안전조치)',False,False),
    ('산업안전보건법 제37조(안전조치 의무)',False,False),
    ('산업안전보건법 제37조(안전조치) 제2항',False,False),
    ('산업안전보건법 제37조(안전조치) 제1항 제2호',False,False),
])
def test_unresolved_citation_stays_search_only(text,duplicate,deleted):
    service,_=law_service(duplicate,deleted)
    result=service.resolve_text(text)
    assert result['text']==text and not result['items'][0]['verified']
    assert 'lsSc.do?' in result['items'][0]['url']


def test_exact_source_article_wins_even_with_duplicate_titles_and_subdivisions():
    service,_=law_service(duplicate=True)
    value=service.resolve_text('산업안전보건법 제38조(안전 조치) 제1항 제1호')
    assert value['items'][0]['verified'] and '제38조(안전조치) 제1항 제1호' in value['text']


def test_failed_law_does_not_remove_other_valid_reference_or_mutate_report_source():
    service,_=law_service(duplicate=True)
    text='산업안전보건법 제37조(안전조치); 산업안전보건법 제39조(보건조치)'
    result=service.resolve_text(text)
    assert [r['verified'] for r in result['items']]==[False,True]
    source=[{'before':{'law':'산업안전보건법 제37조(안전조치)'}}]
    service,_=law_service();output=verified_records(source,service)
    assert '제37조' in source[0]['before']['law'] and '제38조' in output[0]['before']['law']
    offline,_=law_service(fail=True)
    assert not offline.resolve(text)[0]['verified']


@pytest.mark.parametrize('org_id',ORGS)
def test_60_independent_anchors_and_all_300_mapping_pairs(org_id):
    org=load_organization(org_id);cases=cases_for(org_id)
    assert len(cases)==60 and sum(c['split']=='holdout' for c in cases)==24
    for case in cases:
        _,_,items=resolve([case['observation']],org.policy,optional=True,evidence_text=case['description'])
        assert {k:items[0][k] for k in case['expected']}==case['expected'],case['id']
        assert 1<=items[0]['_internal_risk']['score']<=300
    for l in range(1,16):
        for s in range(1,21):
            assert calculate(l,s,org.policy)[0]==org.policy.risk((l+2)//3,(s+4)//5)


@pytest.mark.parametrize('org_id',ORGS)
def test_unknown_always_has_draft_and_at_most_two_optional_questions(org_id):
    org=load_organization(org_id)
    item=facts();item.update({f:'unknown' for f in ('exposure','contact','controls','condition','consequence','extent')})
    _,questions,items=resolve([item]*4,org.policy,optional=True)
    assert len(items)==4 and 0<len(questions)<=2
    assert all(q['options'][-1]=={'value':'unknown','label':'잘 모르겠어요'} for q in questions)
    assert all(r['_internal_risk']['defaulted_facts']['controls']!='effective' for r in items)


def test_quantitative_rules_are_fowi_only_and_require_explicit_units():
    item=facts();item.update(hazard='chemical',exposure_percent=100)
    fowi=load_organization('fowi').policy;other=load_organization('kywa').policy
    assert resolve([item],fowi,optional=True,evidence_text='노출수준 100%')[2][0]['p']==5
    assert resolve([item],fowi,optional=True,evidence_text='수치 없음')[2][0]['p']==3
    assert resolve([item],other,optional=True,evidence_text='노출수준 100%')[2][0]['p']==3


@pytest.mark.parametrize('org_id',ORGS)
@pytest.mark.parametrize('hazard',['electric_shock','fall_from_height','entanglement','collapse','fire_explosion'])
def test_credible_fatal_risk_cannot_be_capped_as_minor_damage(org_id,hazard):
    scenes={'electric_shock':'활선 충전부에 직접 접촉하여 감전 위험','fall_from_height':'높이 3m 작업대에서 추락 위험',
        'entanglement':'가동 중 회전체에 끼임 위험','collapse':'토사와 축대 붕괴로 매몰 위험','fire_explosion':'가연성 증기가 축적되어 점화원으로 폭발 위험'}
    item=facts();item.update(hazard=hazard,hazard_active=True,consequence='minor',scenario=scenes[hazard])
    result=resolve([item],load_organization(org_id).policy,optional=True)[2][0]
    assert result['s']==4 and not result['_internal_risk']['minor_cap_applied']


def test_fire_category_or_active_label_alone_is_not_a_fatal_mechanism():
    item=facts();item.update(category='화재 안전',hazard='fire_explosion',hazard_active=True,
        scenario='소화기 위치 표지의 작은 훼손',consequence='first_aid')
    assert resolve([item],load_organization('kywa').policy,optional=True)[2][0]['s']==2


@pytest.mark.parametrize('org_id',ORGS)
def test_rotation_four_turns_restores_base_and_retry_is_idempotent(org_id,tmp_path):
    cfg=Settings(_env_file=None,organization_id=org_id,app_base_url='http://testserver',demo_data_path=str(tmp_path/'data.json'))
    c,app,repo,drive=connect(cfg)
    raw=io.BytesIO();im=Image.new('RGB',(90,50),'#67899a');im.paste('#e03050',(0,0,20,30));im.save(raw,'JPEG')
    prepared=c.post('/api/photos/prepare',files={'photo':('orientation.jpeg',raw.getvalue(),'image/jpeg')}).json()
    base=c.get(prepared['url']).content;current=prepared
    for index in range(4):
        body={'request_id':str(uuid.uuid4()),'quarter_turns':1}
        response=c.post(f"/api/photos/{current['id']}/rotate",json=body)
        assert response.status_code==200,response.text
        again=c.post(f"/api/photos/{current['id']}/rotate",json=body)
        assert again.json()['id']==response.json()['id']
        current=response.json();picture=c.get(current['url']).content
        assert Image.open(io.BytesIO(picture)).size==((50,90) if index%2==0 else (90,50))
        assert not current['processed']
    assert picture==base
    no_csrf=c.headers.pop('X-CSRF-Token')
    assert c.post(f"/api/photos/{current['id']}/rotate",json={'request_id':str(uuid.uuid4()),'quarter_turns':1}).status_code==403
    c.headers['X-CSRF-Token']=no_csrf
    assert c.post('/api/drafts/reset',json={}).status_code==200
    assert c.get(current['url']).status_code==409
    c.close()


def test_rotation_rejects_other_session_and_invalid_direction(tmp_path):
    cfg=Settings(_env_file=None,app_base_url='http://testserver',demo_data_path=str(tmp_path/'data.json'))
    c,app,_,_=connect(cfg)
    out=io.BytesIO();Image.new('RGB',(80,40)).save(out,'JPEG')
    item=c.post('/api/photos/prepare',files={'photo':('x.jpg',out.getvalue(),'image/jpeg')}).json()
    for value in (0,2,True,'1'):
        assert c.post(f"/api/photos/{item['id']}/rotate",json={'request_id':str(uuid.uuid4()),'quarter_turns':value}).status_code==422
    from fastapi.testclient import TestClient
    other=TestClient(app,base_url=cfg.app_base_url);boot=other.get('/api/bootstrap').json();other.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot['csrf']})
    assert other.post(f"/api/photos/{item['id']}/rotate",json={'request_id':str(uuid.uuid4()),'quarter_turns':1}).status_code==409
    other.close();c.close()


def production_context(tmp_path,monkeypatch,org_id='kywa'):
    from backend.pin_auth import make_pin_hash
    import backend.law_links
    service,_=law_service()
    monkeypatch.setattr(backend.law_links,'LawLinks',lambda *a,**kw:service)
    class AI:
        settings=SimpleNamespace(demo=False)
        def __init__(self):self.calls=0
        def observe(self,*args):
            self.calls+=1;item=facts();item.update(controls='unknown',extent='moderate',law='산업안전보건법 제37조(안전조치)');return [item]
        def observe_after(self,*args):return self.observe()
        def _generate(self,prompt,schema,photo,**kwargs):return schema.model_validate({'faces':[]})
    cfg=Settings(_env_file=None,organization_id=org_id,app_env='production',app_base_url='https://testserver',demo_data_path=str(tmp_path/'data.json'),
        session_secret='synthetic-v13-session-key-'*3,auth_mode='pin',admin_pin_hash=make_pin_hash('2468'),allow_legacy_writes=True,
        google_service_account_json=json.dumps({'type':'service_account','client_email':load_organization('kywa').storage.expected_service_account,'private_key':'test-placeholder'}),
        gemini_api_key='test-placeholder',kosha_api_key='test-placeholder')
    ai=AI();c,app,repo,drive=connect(cfg,ai=ai)
    return c,app,repo,drive,ai,cfg


@pytest.mark.parametrize('org_id',ORGS)
def test_each_institution_default_path_submits_only_its_public_matrix(tmp_path,monkeypatch,org_id):
    c,app,repo,drive,ai,cfg=production_context(tmp_path,monkeypatch,org_id)
    form={'facility':cfg.organization.facilities[0],'description':'기관별 합성 검증'}
    if cfg.organization.department_enabled:form['department']=cfg.organization.departments[0]
    result=c.post('/api/analyses',data=form);assert result.status_code==200,result.text
    item=result.json()['items'][0]
    expected=cfg.organization.policy.risk(item['p'],item['s'])
    assert (item['score'],item['grade'])==(expected['score'],expected['grade'])
    body=submit_body(result.json())
    if cfg.organization.submitter_name.mode=='disabled':body.pop('submitter_name')
    response=c.post('/api/assessments',json=body);assert response.status_code==200,response.text
    row=next(r for r in repo.records() if r['id']==response.json()['ids'][0])
    assert row['before']['_internal_risk']['version'].startswith(org_id+'-facts-')
    assert row['before']['law']==item['law'] and '_internal' not in result.text
    c.close()


def test_optional_draft_can_submit_and_confirm_uses_new_identity_without_ai(tmp_path,monkeypatch):
    c,app,repo,drive,ai,cfg=production_context(tmp_path,monkeypatch)
    form={'facility':cfg.organization.facilities[0],'department':cfg.organization.departments[0],'description':'합성 시험 설명'}
    first=c.post('/api/analyses',data=form).json()
    assert first['items'] and len(first['questions'])==1
    assert first['items'][0]['law']=='산업안전보건법 제38조(안전조치)'
    assert '_internal' not in json.dumps(first)
    # Optional means the unconfirmed draft can be submitted.
    saved=c.post('/api/assessments',json=submit_body(first));assert saved.status_code==200,saved.text
    row=next(r for r in repo.records() if r['id']==saved.json()['ids'][0])
    assert row['before']['law']==first['items'][0]['law'] and row['before']['_internal_law']['changes']
    second=c.post('/api/analyses',data=form).json();assert ai.calls==1
    body={'answers':[{'index':0,'field':'controls','value':'none'}]}
    updated=c.post(f"/api/analyses/{second['draft_id']}/confirm",json=body)
    assert updated.status_code==200,updated.text
    assert updated.json()['draft_id']!=second['draft_id'] and ai.calls==1
    assert c.post(f"/api/analyses/{second['draft_id']}/confirm",json=body).json()['draft_id']==updated.json()['draft_id']
    assert c.post('/api/assessments',json=submit_body(second)).status_code==409
    public=c.get('/api/law-links',params={'text':'산업안전보건법 제37조(안전조치)'})
    assert public.json()['text']=='산업안전보건법 제38조(안전조치)' and '_internal' not in public.text
    assert c.post('/api/auth/pin',data={'pin':'2468'}).status_code==200
    assert '_internal' not in c.get('/api/assessments').text
    c.close()


def test_rotate_processed_photo_invalidates_initial_and_after_drafts(tmp_path,monkeypatch):
    c,app,repo,drive,ai,cfg=production_context(tmp_path,monkeypatch)
    out=io.BytesIO();Image.new('RGB',(90,50),'#2175a0').save(out,'JPEG')
    prepared=c.post('/api/photos/prepare',files={'photo':('test.jpeg',out.getvalue(),'image/jpeg')}).json()
    processed=c.post(f"/api/photos/{prepared['id']}/deidentify",json={}).json()
    form={'facility':cfg.organization.facilities[0],'department':cfg.organization.departments[0],'description':'합성 시험','photo_ids':[processed['id']]}
    initial=c.post('/api/analyses',data=form).json()
    c.post('/api/auth/pin',data={'pin':'2468'})
    c.headers['X-CSRF-Token']=c.get('/api/bootstrap').json()['csrf']
    record=repo.records()[0]
    after=c.post(f"/api/assessments/{record['id']}/reassess",data={'text':'합성 조치','photo_id':processed['id']})
    assert after.status_code==200 and 'p' in after.json(),after.text
    rotated=c.post(f"/api/photos/{processed['id']}/rotate",json={'request_id':str(uuid.uuid4()),'quarter_turns':-1})
    assert rotated.status_code==200 and not rotated.json()['processed']
    assert c.post('/api/assessments',json=submit_body(initial)).status_code==409
    body={'draft_id':after.json()['draft_id'],'request_id':str(uuid.uuid4()),'revision':record['revision'],'p':after.json()['p'],'s':after.json()['s'],'complete':False}
    assert c.post(f"/api/assessments/{record['id']}/actions",json=body).status_code==409
    assert c.post('/api/analyses',data={**form,'photo_ids':[rotated.json()['id']]}).status_code==422
    blurred=c.post(f"/api/photos/{rotated.json()['id']}/deidentify",json={})
    assert blurred.status_code==200 and Image.open(io.BytesIO(c.get(blurred.json()['url']).content)).size==(50,90)
    c.close()
