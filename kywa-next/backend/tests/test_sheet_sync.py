"""State-machine tests: row deletion, edit observation, receipts and lost replies."""
import copy
import json
import uuid
from types import SimpleNamespace

import pytest

from backend.compact_storage import VISIBLE, visible
from backend.domain import digest
from backend.organization import load_organization
from backend.sheet_sync import CONFIG, Store, SyncError, blank, fingerprint, prepare
from backend.tests.test_institutions import current_record


def test_google_snapshot_reads_cells_and_identity_in_one_response():
    from backend.sheet_sync import GoogleRows,KEY
    from backend.repository import cells
    g=GoogleRows.__new__(GoogleRows);g.sid='test';g.sheet_id=1
    g.repo=SimpleNamespace(settings=SimpleNamespace(sheet_name='평가'))
    row=visible(current_record(load_organization('kywa')))
    metadata={'metadataId':12,'metadataKey':KEY,'metadataValue':'stable-id','visibility':'DOCUMENT',
        'location':{'dimensionRange':{'sheetId':1,'dimension':'ROWS','startIndex':1,'endIndex':2}}}
    calls=[]
    def get(**kw):
        calls.append(kw)
        data={'sheets':[{'data':[{'rowData':[{'values':[{'effectiveValue':c['userEnteredValue']} for c in cells(r)['values']]} for r in (VISIBLE,row)],
            'rowMetadata':[{}, {'developerMetadata':[metadata]}]}]}]}
        return SimpleNamespace(execute=lambda:data)
    g.api=SimpleNamespace(get=get)
    rows,identities,_,_=g.snapshot()
    assert len(calls)==1 and 'rowMetadata(developerMetadata)' in calls[0]['fields']
    assert rows[1]==row and identities['stable-id']=={'row':1,'metadata_id':12}


class Rows:
    def __init__(self):
        self.sheet_id=1
        self.rows=[VISIBLE.copy()]; self.ids={}; self.notes={}; self.meta={}; self.events=[]
        self.next_id=1; self.lost_save=False; self.lost_patch=False; self.before_patch=None
        self.table_end=1; self.append_count=0
        self.meta[CONFIG]=(1,{'version':2,'formats':[{'textFormat':{'fontFamily':'Roboto','fontSize':10}} for _ in range(19)]})

    def entries(self): return copy.deepcopy(self.meta)
    def snapshot(self): return copy.deepcopy((self.rows,self.ids,self.notes,{1:[{}]*19}))
    def bind(self,key,index): return {'bind':(key,index)}
    def batch(self,requests):
        for r in requests:
            if 'bind' in r:
                key,index=r['bind'];self.ids[key]={'row':index,'metadata_id':self.next_id};self.next_id+=1
            elif 'deleteDeveloperMetadata' in r:
                md=r['deleteDeveloperMetadata']['dataFilter']['developerMetadataLookup']['metadataId']
                self.ids={k:v for k,v in self.ids.items() if v['metadata_id']!=md}
            elif 'appendCells' in r:
                while len(self.rows)>1 and blank(self.rows[-1]) and len(self.rows)-1 not in self.notes:self.rows.pop()
                for row in r['appendCells']['rows']:
                    index=len(self.rows); self.rows.append([next(iter(c['userEnteredValue'].values())) for c in row['values']])
                    self.notes[index]=row['values'][0]['note']
                self.append_count+=1
            else: raise AssertionError(r)

    def save(self,changes,events=(),extra=()):
        self.batch(extra)
        for kind,key,value in changes:
            self.meta[(kind,key)]=(self.meta.get((kind,key),(len(self.meta)+1,None))[0],json.loads(json.dumps(value)))
        self.events.extend(copy.deepcopy(events))
        if self.lost_save:
            self.lost_save=False
            raise TimeoutError('lost batch response')

    def patch(self,metadata_id,edits):
        if self.before_patch:
            fn,self.before_patch=self.before_patch,None;fn()
        loc=next((v for v in self.ids.values() if v['metadata_id']==metadata_id),None)
        if not loc:raise SyncError('row_deleted','삭제')
        for col,v in edits.items():self.rows[loc['row']][int(col)]=v
        if self.lost_patch:
            self.lost_patch=False;raise TimeoutError('lost values response')

    def finish_append(self,rows,indexes):
        self.table_end=len(rows)
        for i in indexes:self.notes.pop(i,None)

    def delete(self,index):
        self.rows.pop(index)
        self.ids={k:{**v,'row':v['row']-(v['row']>index)} for k,v in self.ids.items() if v['row']!=index}
        self.notes={i-(i>index):n for i,n in self.notes.items() if i!=index}


def fixture(count=3):
    org=load_organization('kywa');g=Rows();repo=SimpleNamespace(settings=SimpleNamespace(organization=org))
    store=Store(repo,g);records=[]
    for i in range(count):
        r=current_record(org);r.update(operation_id=str(uuid.uuid4()),submit_hash='body',submit_owner='owner')
        r['before']['scenario']=f'위험 {i}';records.append(r);store.append([r])
    return store,g,records


@pytest.mark.parametrize('positions',[(1,),(2,),(3,),(3,1),(3,2,1)])
def test_deletion_never_blocks_append_and_keeps_other_ids(positions):
    store,g,original=fixture()
    deleted={original[i-1]['id'] for i in positions}
    for i in positions:g.delete(i)
    assert {r['id'] for r in store.sync()[0]}=={r['id'] for r in original}-deleted
    new=current_record(store.org);new.update(operation_id=str(uuid.uuid4()),submit_hash='new',submit_owner='owner')
    store.append([new]); assert g.rows[-1][5]==new['before']['scenario']
    assert g.ids[new['id']]['row']==len(g.rows)-1
    assert len(store.sync()[0])==4-len(positions)
    assert all(g.meta[('record',key)][1]['deleted'] for key in deleted)
    assert len(g.rows[0])==19


@pytest.mark.parametrize('index',[1,2,3])
def test_cleared_rows_append_after_last_data(index):
    store,g,records=fixture();g.rows[index]=['']*19
    new=current_record(store.org);new.update(operation_id=str(uuid.uuid4()),submit_hash='new',submit_owner='owner')
    store.append([new])
    assert g.ids[new['id']]['row']==(3 if index==3 else 4)
    assert records[index-1]['id'] not in {r['id'] for r in store.sync()[0]}
    assert g.meta[CONFIG][1]['formats'][0]['textFormat']['fontFamily']=='Roboto'


def test_identical_submissions_and_streamlit_rows_do_not_merge():
    store,g,records=fixture(1)
    g.rows.extend([g.rows[1].copy(),g.rows[1].copy()])
    found,_=store.sync();assert len(found)==3 and len({r['id'] for r in found})==3
    g.delete(1)
    assert len(store.sync()[0])==2
    assert len({r['id'] for r in store.sync()[0]})==2


def test_lost_append_response_restart_retry_is_once():
    store,g,_=fixture(0);record=current_record(store.org)
    record.update(operation_id=str(uuid.uuid4()),submit_hash='body',submit_owner='owner')
    g.lost_save=True
    with pytest.raises(TimeoutError):store.append([record])
    restarted=Store(store.repo,g);restarted.append([record])
    assert g.append_count==1 and len(restarted.sync()[0])==1 and not g.notes
    g.delete(1)
    receipt=restarted.recover_append(record['operation_id'])
    assert receipt[0]['_sheet_deleted']
    with pytest.raises(SyncError,match='삭제'):restarted.append([record])
    assert len(g.rows)==1


def test_append_deleted_before_binding_is_not_resurrected():
    store,g,_=fixture(0);record=current_record(store.org)
    record.update(operation_id=str(uuid.uuid4()),submit_hash='body',submit_owner='owner')
    g.lost_save=True
    with pytest.raises(TimeoutError):store.append([record])
    g.delete(1)
    assert store.recover_append(record['operation_id'])[0]['_sheet_deleted']
    assert len(g.rows)==1


def test_direct_text_edits_and_masked_name_have_history_once():
    store,g,records=fixture(1);g.rows[1][5]='새 위험상황';g.rows[1][10]='새 감소대책';g.rows[1][18]='홍길동'
    found,issues=store.sync();assert not issues
    assert found[0]['before']['scenario']=='새 위험상황' and found[0]['submitter_name']=='홍㉠㉢'
    assert found[0]['revision']==2
    event=g.events[-1];assert event['actor']=='' and event['sheet_before'][5]!=event['sheet_after'][5]
    store.sync();assert len(g.events)==1


@pytest.mark.parametrize('changes', [{6:5,7:3},{8:99},{9:'임의 등급'}])
def test_known_policy_recalculates_score_and_grade(changes):
    store,g,_=fixture(1)
    for i,v in changes.items():g.rows[1][i]=v
    found,issues=store.sync();assert not issues
    assert found[0]['before']['score']==15 and g.rows[1][8:10]==[15,'높음']


def test_bad_row_isolated_new_submission_allowed_then_repaired():
    store,g,_=fixture(2);g.rows[1][6]='잘못된 숫자'
    records,issues=store.sync();assert len(records)==1 and issues[0]['row']==2
    assert issues[0]['code']=='row_invalid'
    r=current_record(store.org);r.update(operation_id=str(uuid.uuid4()),submit_hash='x',submit_owner='owner')
    store.append([r]);assert len(store.sync()[0])==2
    g.rows[1][6]=1;records,issues=store.sync();assert len(records)==3 and not issues
    assert g.rows[1][8]==3


def test_partial_clear_is_not_deletion():
    store,g,original=fixture(1);g.rows[1][5]=''
    records,issues=store.sync();assert not records and len(issues)==1
    assert not g.meta[('record',original[0]['id'])][1].get('deleted')


def test_unknown_policy_preserves_old_grade_until_confirmed():
    store,g,_=fixture(0)
    r=current_record(store.org);r.update(policy='LEGACY-UNKNOWN');r.pop('policy_snapshot')
    r['before'].update(score=15,grade='보통');g.rows.append(visible(r))
    records,issues=store.sync();assert not issues and records[0]['before']['grade']=='보통'
    g.rows[1][6]=4
    records,issues=store.sync();assert not records and issues[0]['can_confirm_policy']
    issue=issues[0];operation=str(uuid.uuid4())
    with pytest.raises(SyncError):store.confirm(issue['id'],issue['revision']-1,operation,'admin')
    store.confirm(issue['id'],issue['revision'],operation,'admin')
    records,issues=store.sync();assert not issues
    assert records[0]['policy']==store.org.policy.version and records[0]['before']['score']==12
    assert g.rows[1][8:10]==[12,'약간 높음']
    store.confirm(records[0]['id'],issue['revision'],operation,'admin')
    assert sum(e['kind']=='현재 KYWA 기준 적용' for e in g.events)==1


def test_new_after_scores_are_in_progress_and_action_text_retained():
    store,g,_=fixture(1);g.rows[1][13:17]=[1,2,'','']
    records,issues=store.sync();assert not issues and records[0]['status']=='조치 중'
    assert g.rows[1][15:17]==[2,'매우 낮음']
    r=records[0];r.update(revision=r['revision']+1,status='완료');r['after'].update(text='안전조치',created_at='2026-11-01T09:00:00+09:00')
    store.update([r],[])
    g.rows[1][13]=2
    records,issues=store.sync();assert not issues
    assert records[0]['status']=='조치 중' and records[0]['after']['text']=='안전조치'


def test_app_draft_conflict_does_not_overwrite_sheet():
    store,g,_=fixture(1);r=store.sync()[0][0]
    g.rows[1][5]='시트에서 수정';r.update(revision=r['revision']+1,status='조치 중')
    with pytest.raises(SyncError,match='변경'):store.update([r],[])
    assert g.rows[1][5]=='시트에서 수정'


def test_action_recovers_lost_response_without_duplicate_audit():
    store,g,_=fixture(1);r=store.sync()[0][0]
    r.update(revision=2,status='완료',after={**store.org.policy.risk(1,1),'text':'실제 조치','policy':store.org.policy.version})
    event={'id':str(uuid.uuid4()),'record_id':r['id'],'kind':'완료','at':'2026-11-02','actor':'admin','text':'실제 조치'}
    g.lost_patch=True
    with pytest.raises(TimeoutError):store.update([r],[event])
    restarted=Store(store.repo,g);records,issues=restarted.sync()
    assert not issues and records[0]['after']['text']=='실제 조치' and records[0]['status']=='완료'
    restarted.sync();assert sum(e['id']==event['id'] for e in g.events)==1


def test_row_shift_between_read_and_update_targets_identity():
    store,g,_=fixture(2);r=store.sync()[0][1]
    r.update(revision=2,status='완료',after={**store.org.policy.risk(1,1),'text':'조치'})
    g.before_patch=lambda:g.delete(1)
    store.update([r],[])
    found=store.sync()[0];assert len(found)==1 and found[0]['id']==r['id'] and found[0]['after']['score']==1


def test_migration_preserves_identity_and_tombstones_missing():
    store,g,records=fixture(3);g.meta.pop(CONFIG);g.ids={}
    g.delete(2)
    plan=prepare(store.repo,g);assert plan['matched']==2 and plan['deleted']==1
    prepare(store.repo,g,True)
    assert {r['id'] for r in store.sync()[0]}=={records[0]['id'],records[2]['id']}
    assert prepare(store.repo,g,True)=={'already_prepared':True}


def test_ambiguous_migration_stops_without_writing():
    store,g,_=fixture(1);g.meta.pop(CONFIG);g.ids={};g.rows.append(g.rows[1].copy())
    before=copy.deepcopy(g.meta)
    with pytest.raises(SyncError,match='모호'):prepare(store.repo,g,True)
    assert g.meta==before


def test_report_signature_ignores_shift_but_not_content_or_deletion():
    from backend.report_jobs import signature
    store,g,_=fixture(2);records=store.sync()[0]
    changed=copy.deepcopy(records);changed[0]['_sheet_row']=50
    assert signature(changed)==signature(records)
    changed[0]['before']['scenario']='변경'
    assert signature(changed)!=signature(records)
    assert signature(records[:1])!=signature(records)


@pytest.fixture
def api_context(tmp_path):
    import threading
    from fastapi.testclient import TestClient
    from backend.config import Settings
    from backend.main import create_app
    store,g,records=fixture(2)
    repo=SimpleNamespace(lock=threading.RLock(),records=lambda:store.sync()[0],snapshot=store.sync,
        receipt=store.recover_append,confirm_policy=store.confirm,
        events=lambda key=None:[e for e in g.events if not key or e['record_id']==key],
        apply=lambda rs,es:store.update(rs,es) if '_sheet_row' in rs[0] else store.append(rs))
    cfg=Settings(_env_file=None,app_env='demo',app_base_url='http://testserver',demo_data_path=str(tmp_path/'demo.json'))
    with TestClient(create_app(cfg,repo=repo)) as client:
        csrf=client.get('/api/bootstrap').json()['csrf']
        client.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':csrf})
        yield client,store,g,repo


def test_api_submit_does_not_decode_unrelated_bad_or_deleted_rows(api_context):
    from backend.tests.test_system import initial
    c,store,g,repo=api_context
    g.delete(1);g.rows[1][6]='invalid'
    repo.records=lambda:pytest.fail('submission must use request receipt, never full records')
    body=initial(c)
    first=c.post('/api/assessments',json=body);assert first.status_code==200
    assert c.post('/api/assessments',json=body).json()['replayed']
    g.delete(len(g.rows)-1)
    response=c.post('/api/assessments',json=body)
    assert response.status_code==409 and response.json()['code']=='row_deleted'
    assert len(g.rows)==2


@pytest.mark.parametrize('format',['xlsx','pdf','hwpx'])
def test_api_report_rejects_invalid_rows_and_stale_download(api_context,format):
    import time
    from backend.tests.test_system import login
    c,store,g,_=api_context;login(c)
    body={'format':format}
    started=c.post('/api/report-jobs',json=body);assert started.status_code==200
    job=started.json()['id'];path=f'/api/report-jobs/{job}'
    for _ in range(100):
        if c.get(path).json()['state']=='complete':break
        time.sleep(.02)
    assert c.get(path+'/download').status_code==200
    g.delete(1)
    response=c.get(path+'/download')
    assert response.status_code==409 and response.json()['code']=='report_stale'
    g.rows[1][0]='bad date'
    listing=c.get('/api/assessments').json();assert not listing['items'] and listing['issues'][0]['row']==2
    for path in ('/api/reports','/api/report-jobs'):
        if path=='/api/reports' and format=='hwpx': continue
        response=c.post(path,json=body)
        assert response.status_code==409 and response.json()['code']=='report_invalid_rows'
    overview=c.get('/api/overview').json();assert overview['total']==0
    assert 'issues' not in overview and 'submitter_name' not in json.dumps(overview)


def test_policy_api_requires_admin_csrf_revision_and_hides_raw_audit(api_context):
    from backend.tests.test_system import login
    c,store,g,_=api_context
    g.rows.append(g.rows[1].copy());store.sync();g.rows[3][8]=999
    login(c,'staff')
    issue=c.get('/api/assessments').json()['issues'][0]
    path=f"/api/assessments/{issue['id']}/policy"
    body={'request_id':str(uuid.uuid4()),'revision':issue['revision']}
    assert c.post(path,json=body).status_code==403
    login(c)
    assert c.post(path,json=body,headers={'X-CSRF-Token':'invalid'}).status_code==403
    assert c.post(path,json={**body,'revision':1}).status_code==409
    assert c.post(path,json=body).status_code==200
    assert c.post(path,json=body).status_code==200
    history=c.get(f"/api/assessments/{issue['id']}/history").json()
    assert all('sheet_before' not in e and 'sheet_after' not in e for e in history['items'])
