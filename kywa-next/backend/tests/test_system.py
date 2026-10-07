import copy
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import Settings
from backend.domain import risk, HEADERS, sheet_row
from backend.main import create_app
from backend.migrate import migration_rows
from backend.repository import DemoRepository, DriveStore, cells
from backend.services import Drafts, ServiceError, prepare_image


@pytest.fixture
def context(tmp_path):
    cfg = Settings(_env_file=None, app_env='demo', app_base_url='http://testserver', demo_data_path=str(tmp_path/'data.json'))
    repo = DemoRepository(cfg.demo_data_path)
    app = create_app(cfg, repo=repo)
    with TestClient(app) as client:
        csrf = client.get('/api/bootstrap').json()['csrf']
        client.headers.update({'Origin':cfg.app_base_url, 'X-CSRF-Token':csrf})
        yield client, app, repo, cfg


def login(client, role='admin'):
    assert client.post('/api/auth/demo', data={'role':role}).status_code == 200


def initial(client, description='본관 2층 난간 흔들림'):
    response = client.post('/api/analyses', data={'facility':'중앙', 'department':'협력부(국립청소년시설)', 'description':description})
    assert response.status_code == 200, response.text
    draft = response.json()
    return dict(request_id=str(uuid.uuid4()), draft_id=draft['draft_id'], items=[dict(index=i, location='2층', scenario=x['scenario'], solution=x['solution']) for i,x in enumerate(draft['items'])])


@pytest.mark.parametrize('p,s', [(p,s) for p in range(1,6) for s in range(1,5)])
def test_all_twenty_risk_combinations(p,s):
    grades = {1:'매우 낮음',2:'매우 낮음',3:'매우 낮음',4:'낮음',5:'낮음',6:'낮음',8:'보통',9:'약간 높음',10:'약간 높음',12:'약간 높음',15:'높음',16:'매우 높음',20:'매우 높음'}
    assert risk(p,s) == {'p':p,'s':s,'score':p*s,'grade':grades[p*s]}


@pytest.mark.parametrize('p,s', [(True,1),('3',2),(3,4.1),(0,2),(6,1),(1,5)])
def test_invalid_scores_rejected(p,s):
    with pytest.raises(ValueError): risk(p,s)


def test_health_does_not_touch_repository(context, monkeypatch):
    c,app,repo,_=context
    monkeypatch.setattr(repo, 'records', lambda: pytest.fail('health must not read repository'))
    response = c.get('/healthz')
    assert response.json() == {'status':'ok'}
    assert response.headers['cache-control'] == 'no-store'


def test_public_overview_is_aggregate_only_and_refreshes_after_submit(context):
    c, app, repo, _ = context
    data = c.get('/api/overview').json()
    assert data['total'] == 4 and data['completed'] == 1
    assert sum(item['count'] for item in data['categories']) == 4
    assert sum(item['count'] for item in data['facilities']) == 4
    serialized = json.dumps(data, ensure_ascii=False)
    for forbidden in ('photo_id', 'photo_url', 'scenario', 'department', 'actor', 'demo-admin', '사무실 복도'):
        assert forbidden not in serialized
    assert c.get('/api/assessments').status_code == 401
    assert c.post('/api/assessments', json=initial(c)).status_code == 200
    assert c.get('/api/overview').json()['total'] == 5
    assert c.get('/api/overview?year=1999').status_code == 422
    assert c.get('/api/overview?year=0').status_code == 422


def test_overview_year_filter_and_cache(context, monkeypatch):
    c, app, repo, _ = context
    record = repo.records()[0]
    record['created_at'] = '2025-12-31T23:59:59+09:00'
    repo.apply([record], [])
    assert c.get('/api/overview?year=2025').json()['total'] == 1
    monkeypatch.setattr(repo, 'records', lambda: pytest.fail('cached overview must not reread Sheets'))
    assert c.get('/api/overview?year=2024').json()['total'] == 0
    assert 2025 in c.get('/api/overview?year=2024').json()['years']


def test_analysis_recommends_guide_keywords_from_all_items(context):
    c, _, _, _ = context
    data = c.post('/api/analyses', data={'facility':'중앙', 'department':'협력부(국립청소년시설)',
                                      'description':'난간 파손\n감전 위험'}).json()
    assert data['guide_keywords'] == ['난간', '감전']
    from backend.overview import guide_keywords
    assert guide_keywords([{'scenario':'특이사항 없음'}]) == []


def test_anonymous_csrf_and_staff_scope(context):
    c,app,repo,_=context
    assert c.get('/api/assessments').status_code == 401
    assert c.post('/api/auth/demo', data={'role':'admin'}, headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert c.post('/api/auth/demo', data={'role':'admin'}, headers={'Origin':'https://evil.example'}).status_code == 403
    login(c,'staff')
    assert {r['facility'] for r in c.get('/api/assessments').json()['items']} == {'중앙'}
    assert c.get('/api/assessments/demo-2/history').status_code == 404
    assert c.post('/api/reports', json={'format':'pdf'}).status_code == 403
    assert c.post('/api/assessments/demo-2/state',json={'request_id':str(uuid.uuid4()),'revision':1,'status':'조치 중'}).status_code == 404


def test_selected_submit_retry_and_owner_binding(context):
    c,app,repo,_=context
    body=initial(c,'난간 손상\n바닥 미끄러움')
    body['items']=body['items'][1:]
    first=c.post('/api/assessments',json=body)
    assert first.status_code == 200,first.text
    assert len(repo.records()) == 5
    assert c.post('/api/assessments',json=body).json()['replayed'] is True
    assert len(repo.records()) == 5
    body['items'][0]['location']='다른 장소'
    assert c.post('/api/assessments',json=body).status_code == 409
    body['items'][0]['location']='2층'
    c.cookies.clear()
    c.headers['X-CSRF-Token']=c.get('/api/bootstrap').json()['csrf']
    assert c.post('/api/assessments',json=body).status_code == 409


def test_uuid_and_duplicate_indexes_rejected(context):
    c,_,_,_=context
    body=initial(c)
    body['request_id']='-'*36
    assert c.post('/api/assessments',json=body).status_code == 422
    body['request_id']=str(uuid.uuid4())
    body['items']*=2
    assert c.post('/api/assessments',json=body).status_code == 422


def test_action_cycle_history_and_conflicts(context):
    c,app,repo,_=context
    login(c)
    draft=c.post('/api/assessments/demo-1/reassess', data={'text':'고정부 보강 및 흔들림 재점검'}).json()
    body=dict(request_id=str(uuid.uuid4()),draft_id=draft['draft_id'],revision=1,p=2,s=3,complete=True)
    response=c.post('/api/assessments/demo-1/actions',json=body)
    assert response.status_code == 200,response.text
    item=response.json()['item']
    assert item['status']=='완료' and item['after']['score']==6 and item['after']['grade']=='낮음'
    assert c.post('/api/assessments/demo-1/actions',json=body).json()['replayed'] is True
    assert len(c.get('/api/assessments/demo-1/history').json()['items'])==1
    assert c.post('/api/assessments/demo-1/reassess',data={'text':'추가'}).status_code==409
    stale=dict(request_id=str(uuid.uuid4()),revision=1,status='조치 중')
    assert c.post('/api/assessments/demo-1/state',json=stale).status_code==409
    stale['revision']=2
    assert c.post('/api/assessments/demo-1/state',json=stale).status_code==200
    assert c.post('/api/assessments/demo-1/state',json=stale).status_code==200
    assert len(repo.events('demo-1'))==2
    body['request_id']=str(uuid.uuid4())
    assert c.post('/api/assessments/demo-1/actions',json=body).status_code==409
    assert repo.records()[0]['before']['score']==12


def test_parallel_same_submit_stores_once(context):
    c,app,repo,_=context
    body=initial(c)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _:c.post('/api/assessments',json=body),range(5)))
    assert all(r.status_code==200 for r in results)
    assert len(repo.records())==5
    assert sum(not r.json()['replayed'] for r in results)==1


def test_photos_and_foreign_drafts(context):
    c,app,repo,_=context
    raw=io.BytesIO(); Image.new('RGB',(600,400),'navy').save(raw,'PNG')
    upload=c.post('/api/photos/prepare',files={'photo':('image.png',raw.getvalue(),'image/png')})
    assert upload.status_code==200,upload.text
    photo=upload.json()
    response=c.get(photo['url'])
    assert response.status_code==200 and response.content.startswith(b'\xff\xd8')
    analyzed=c.post('/api/analyses',data={'facility':'중앙','department':'협력부(국립청소년시설)','photo_id':photo['id']})
    assert analyzed.status_code==200
    c.cookies.clear();c.headers['X-CSRF-Token']=c.get('/api/bootstrap').json()['csrf']
    assert c.get(photo['url']).status_code==422
    assert c.post('/api/photos/prepare',files={'photo':('bad.jpg',b'fake','image/jpeg')}).status_code==422


def test_failed_face_processing_never_returns_original(monkeypatch):
    import cv2
    raw=io.BytesIO();Image.new('RGB',(100,100),'red').save(raw,'PNG')
    monkeypatch.setattr(cv2,'CascadeClassifier',lambda *_: (_ for _ in ()).throw(RuntimeError('missing model')))
    with pytest.raises(ServiceError): prepare_image(raw.getvalue())


def test_draft_expiry_and_eviction():
    drafts=Drafts(max_entries=1,ttl=-1)
    key=drafts.put('a',{'type':'initial'})
    with pytest.raises(ServiceError):drafts.get('a',key)
    drafts=Drafts(max_entries=1)
    key=drafts.put('a',{})
    drafts.put('b',{})
    with pytest.raises(ServiceError):drafts.get('a',key)


def test_report_exports_korean_photos_formula_protection(context):
    from openpyxl import load_workbook
    from pypdf import PdfReader
    c,app,repo,cfg=context
    login(c)
    record=copy.deepcopy(repo.records()[0])
    record['before']['location']='=HYPERLINK("https://example.com")'
    record['before']['scenario']='긴 한글 위험상황 < & > 검토 ' * 120
    photo=io.BytesIO(); Image.new('RGB',(640,480),'blue').save(photo,'JPEG')
    store=DriveStore(cfg)
    record['photo_id']=store.put(photo.getvalue(),str(uuid.uuid4()))
    record['after']={'p':1,'s':2,'score':2,'grade':'매우 낮음','photo_id':record['photo_id'],'text':'난간 고정 완료','actor':'담당자','created_at':record['created_at']}
    repo.apply([record],[])
    xlsx=c.post('/api/reports',json={'format':'xlsx','facility':'중앙'})
    assert xlsx.status_code==200,xlsx.text[:200]
    wb=load_workbook(io.BytesIO(xlsx.content))
    assert wb['위험성평가']['D2'].data_type=='s'
    assert wb['위험성평가']['D2'].value.startswith("'=")
    assert len(wb['위험성평가']._images)==2
    pdf=c.post('/api/reports',json={'format':'pdf','facility':'중앙'})
    assert pdf.status_code==200,pdf.text[:200]
    document=PdfReader(io.BytesIO(pdf.content))
    text='\n'.join(p.extract_text() for p in document.pages)
    assert '위험성평가' in text and '난간 고정 완료' in text
    assert len(document.pages)>=2


def test_report_filters_empty_invalid_and_limit(context):
    c,app,repo,cfg=context; login(c)
    assert c.post('/api/reports',json={'format':'pdf','facility':'생태'}).status_code==422
    assert c.get('/api/assessments?start=wrong').status_code==422
    assert c.post('/api/reports',json={'format':'pdf','start':'2026-12-01','end':'2026-01-01'}).status_code==422
    cfg.report_max_rows=2
    assert c.post('/api/reports',json={'format':'pdf'}).status_code==422


def test_legacy_migration_preserves_original_values(context):
    _,_,repo,_=context
    row=sheet_row(repo.records()[0])[:18]
    row[0]='2026. 9. 2 오후 3:24:15';row[9]='높음';row[8]=12
    result=migration_rows([HEADERS[:18],row],'sheet')
    index, extra=result[0]
    record=json.loads(extra[-1])
    assert index==1 and record['before']['grade']=='높음' and record['policy']=='LEGACY-UNKNOWN'
    assert record['created_at']=='2026-09-02T15:24:15+09:00'
    assert sheet_row(record)[:13]==row[:13]
    assert migration_rows([HEADERS,row+extra],'sheet')==[]
    with pytest.raises(ValueError):migration_rows([HEADERS,row+['already used']],'sheet')
    with pytest.raises(ValueError):migration_rows([['unknown'],row],'sheet')


def test_google_sheet_text_is_not_a_formula():
    assert cells(['=1+1',3])['values']==[{'userEnteredValue':{'stringValue':'=1+1'}},{'userEnteredValue':{'numberValue':3}}]


def test_production_refuses_incomplete_configuration():
    with pytest.raises(ValueError):Settings(_env_file=None,app_env='production').validate_runtime()
    with pytest.raises(ValueError):Settings(_env_file=None,app_base_url='https://example.com').validate_runtime()


def test_oversize_body_even_without_content_length(context):
    c,_,_,_=context
    response=c.post('/api/assessments', content=(b'x'*1024*1024 for _ in range(12)), headers={'Content-Type':'application/json'})
    assert response.status_code==413
