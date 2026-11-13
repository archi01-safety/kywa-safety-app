import copy
import io
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import Settings
from backend.domain import now
from backend.main import create_app
from backend.repository import DemoRepository
from backend.services import AIService
from backend.detailed_risk import calculate,resolve,Observation,FactAnswer,FACTS
from backend.organization import load_organization
from backend.photo_records import report_slots
from backend.tests.test_system import context,login,initial

ORGS=('kywa','ayf','fowi','knps','knf','kohi','khidi','cayf')


class MemoryDrive:
    def __init__(self):self.items={}
    def put_photo(self,data,key,facility,created_at,after=False):
        if not data:return {'id':'','view_url':'','created_at':created_at}
        if key not in self.items:
            self.items[key]={'id':'test-'+key,'view_url':f'https://drive.google.com/file/d/test-{key}/view?usp=drivesdk','created_at':created_at,'data':data}
        return {k:v for k,v in self.items[key].items() if k!='data'}
    def get(self,key):return next((v['data'] for v in self.items.values() if v['id']==key),None)


def image(color):
    out=io.BytesIO();Image.new('RGB',(320,200),color).save(out,'WEBP');return out.getvalue()


def connect(cfg,**kwargs):
    repo=kwargs.pop('repo',None) or DemoRepository(cfg.demo_data_path,cfg.organization)
    drive=kwargs.pop('drive',None) or MemoryDrive()
    app=create_app(cfg,repo=repo,drive=drive,**kwargs)
    c=TestClient(app,base_url=cfg.app_base_url)
    csrf=c.get('/api/bootstrap').json()['csrf'];c.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':csrf})
    return c,app,repo,drive


def upload(c,color):
    # Deliberately a WebP payload named JPG, the real-world regression case.
    prepared=c.post('/api/photos/prepare',files={'photo':('renamed.jpg',image(color),'image/jpeg')})
    assert prepared.status_code==200,prepared.text
    result=c.post(f"/api/photos/{prepared.json()['id']}/deidentify",json={})
    assert result.status_code==200,result.text
    return result.json()['id']


def submit_body(draft):
    return {'submitter_name':'홍㉠㉢','request_id':str(uuid.uuid4()),'draft_id':draft['draft_id'],
        'items':[{'index':0,'location':'시험 위치','scenario':'시험 걸림 위험','solution':'시험 통로 정리'}]}


def test_two_photos_order_limit_retry_and_authorized_read(tmp_path):
    cfg=Settings(_env_file=None,app_base_url='http://testserver',demo_data_path=str(tmp_path/'data.json'))
    c,app,repo,drive=connect(cfg)
    first,second=upload(c,'blue'),upload(c,'yellow')
    form={'facility':cfg.organization.facilities[0],'department':cfg.organization.departments[0],'description':'같은 통로의 전체와 근접 사진','photo_ids':[first,second]}
    draft=c.post('/api/analyses',data=form).json()
    assert len(draft['photo_urls'])==2 and draft['photo_urls'][0].endswith(first+'/photo')
    body=submit_body(draft);response=c.post('/api/assessments',json=body)
    assert response.status_code==200,response.text
    assert c.post('/api/assessments',json=body).json()['replayed']
    assert len(drive.items)==2
    stored=next(r for r in repo.records() if r['id']==response.json()['ids'][0])
    assert stored['photo_ids'][0]==stored['photo_id'] and len(stored['photo_ids'])==2
    assert stored['photo_view_urls'][1].endswith('?usp=drivesdk')
    assert c.get(f"/api/assessments/{stored['id']}/photos/{stored['photo_ids'][1]}").status_code==401
    login(c)
    listed=next(r for r in c.get('/api/assessments').json()['items'] if r['id']==stored['id'])
    assert len(listed['photo_urls'])==2
    assert all(c.get(url).status_code==200 for url in listed['photo_urls'])
    assert c.get(f"/api/assessments/{stored['id']}/photos/not-owned").status_code==404
    assert c.post('/api/analyses',data={**form,'photo_ids':[first,second,first]}).status_code==422
    assert c.post('/api/analyses',data={**form,'photo_ids':[first,first]}).status_code==422
    distinct=c.post('/api/assessments',json={**body,'request_id':str(uuid.uuid4())})
    assert distinct.status_code==200 and distinct.json()['ids']!=response.json()['ids']
    c.close()


def test_plan_does_not_require_ai_and_is_idempotent_and_versioned(context):
    c,app,repo,cfg=context;login(c)
    record=repo.records()[0];body={'request_id':str(uuid.uuid4()),'revision':record['revision'],'text':'손상된 난간을 보강할 예정','due_date':'2026-12-01'}
    first=c.post(f"/api/assessments/{record['id']}/plan",json=body)
    assert first.status_code==200,first.text
    item=first.json()['item'];assert item['status']=='조치예정' and not item['after']
    assert item['plan']['text']==body['text'] and item['revision']==record['revision']+1
    assert c.post(f"/api/assessments/{record['id']}/plan",json=body).json()['replayed']
    assert c.get('/api/assessments?status=조치예정').json()['items'][0]['id']==record['id']
    assert c.post(f"/api/assessments/{record['id']}/plan",json={**body,'text':'변경된 내용'}).status_code==409
    assert c.post(f"/api/assessments/{record['id']}/plan",json={**body,'request_id':str(uuid.uuid4())}).status_code==409
    assert c.post(f"/api/assessments/{record['id']}/plan",json={**body,'due_date':'2026-02-30'}).status_code==422
    assert len(repo.events(record['id']))==1


@pytest.mark.parametrize('org_id',ORGS)
def test_all_300_pairs_preserve_public_institution_matrix(org_id):
    policy=load_organization(org_id).policy
    for likelihood in range(1,16):
        for severity in range(1,21):
            result,l,s=calculate(likelihood,severity,policy)
            assert result==policy.risk((likelihood+2)//3,(severity+4)//5)
            assert l*s in range(1,301)
    assert policy.risk(5,3)['score']==15


def facts(**changes):
    return Observation(category='시설 안전',location='시험 통로',scenario='바닥 케이블 걸림 위험',solution='통로 밖으로 정리',law='산업안전보건기준에 관한 규칙 제3조(전도의 방지)',
        exposure='daily',contact='possible',controls='partial',condition='stable',consequence='first_aid',extent='limited',**changes).model_dump()


def test_unknown_is_not_assumed_and_answer_validation():
    data=facts();data['controls']='unknown';policy=load_organization('kywa').policy
    observed,questions,result=resolve([data],policy)
    assert not result and len(questions)==1 and questions[0]['field']=='controls'
    assert not any('score' in option for option in questions[0]['options'])
    values,q,items=resolve(observed,policy,[FactAnswer(index=0,field='controls',value='partial')])
    assert not q and items[0]['score']==6 and 1<=items[0]['_internal_risk']['score']<=300
    with pytest.raises(ValueError):resolve(values,policy,[FactAnswer(index=0,field='controls',value='none')])


def test_production_observations_cached_and_private(tmp_path):
    from backend.pin_auth import make_pin_hash
    class AI:
        settings=SimpleNamespace(demo=False)
        def __init__(self):self.calls=0
        def observe(self,*args):
            self.calls+=1;item=facts();item['controls']='unknown';return [item]
    cfg=Settings(_env_file=None,app_env='production',app_base_url='https://testserver',demo_data_path=str(tmp_path/'data.json'),
        session_secret='test-only-session-key-'*3,auth_mode='pin',admin_pin_hash=make_pin_hash('2468'),allow_legacy_writes=True,
        google_service_account_json=json.dumps({'type':'service_account','client_email':load_organization('kywa').storage.expected_service_account,'private_key':'test-placeholder'}),
        gemini_api_key='test-placeholder',kosha_api_key='test-placeholder',detailed_risk_enabled=True)
    ai=AI();c,app,repo,drive=connect(cfg,ai=ai)
    form={'facility':cfg.organization.facilities[0],'department':cfg.organization.departments[0],'description':'동일한 시험 관찰'}
    result=c.post('/api/analyses',data=form)
    assert result.status_code==200,result.text
    pending=result.json();assert len(pending['questions'])==1
    response=c.post(f"/api/analyses/{pending['draft_id']}/confirm",json={'answers':[{'index':0,'field':'controls','value':'partial'}]})
    assert response.status_code==200,response.text
    assert response.json()['items'][0]['score']==6 and '_internal' not in response.text
    body=submit_body(response.json());saved=c.post('/api/assessments',json=body)
    assert saved.status_code==200,saved.text
    assert c.post('/api/analyses',data=form).status_code==200 and ai.calls==1
    assert c.post('/api/auth/pin',data={'pin':'2468'}).status_code==200
    assert '_internal' not in c.get('/api/assessments').text
    record=next(r for r in repo.records() if r['id']==saved.json()['ids'][0])
    assert record['before']['_internal_risk']['version']
    c.close()


@pytest.mark.parametrize('before,after,labels',[
    ([],False,['개선 전','개선 후']),(['a'],True,['개선 전','개선 후']),
    (['a','b'],False,['개선 전 ①','개선 전 ②']),(['a','b'],True,['개선 전 ①','개선 전 ②','개선 후'])])
def test_report_layout_uses_three_columns_only_for_three_photos(before,after,labels):
    r={'photo_ids':before,'photo_id':before[0] if before else '', 'after':{'photo_id':'after'} if after else None}
    assert [label for label,_ in report_slots(r)]==labels
