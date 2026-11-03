import copy
from types import SimpleNamespace
import pytest
from backend.organization import load_organization
from backend.compact_storage import visible, VISIBLE
from backend.visible_layout import VisibleLayout
from backend.migrate_ayf import plan
from backend.sheet_schema import SheetSchemaError
from backend.sheet_sync import GoogleRows
from backend.repository import cells
from backend.tests.test_institutions import current_record


def test_17_roundtrip_and_legacy_19():
    org = load_organization('ayf')
    header = [v for i,v in enumerate(VISIBLE) if i not in (2,18)]
    row = visible(current_record(org))
    for h in (header, VISIBLE):
        adapter = VisibleLayout(h, org)
        assert adapter.canonical(adapter.physical(row)) == row
    assert len(VisibleLayout(header, org).physical(row)) == 17
    with pytest.raises(SheetSchemaError): VisibleLayout(header, load_organization('kywa'))


def test_ayf_migration_is_scoped_reentrant_and_rejects_pending():
    org=load_organization('ayf')
    assert plan(VISIBLE,org,{}) == ([18,2],[])
    header=[v for i,v in enumerate(VISIBLE) if i not in (2,18)]
    assert plan(header,org,{}) == ([],[])
    with pytest.raises(SheetSchemaError): plan(VISIBLE,load_organization('kywa'),{})
    with pytest.raises(SheetSchemaError): plan(VISIBLE,org,{('request','r'):(1,{'state':'appending'})})


def test_google_17_snapshot_append_and_patch_map():
    org=load_organization('ayf');header=[v for i,v in enumerate(VISIBLE) if i not in (2,18)]
    row=visible(current_record(org));adapter=VisibleLayout(header,org)
    calls=[]
    def get(**kw):
        data={'sheets':[{'data':[{'rowData':[{'values':[{'effectiveValue':c['userEnteredValue']} for c in cells(r)['values']]+[{},{}]} for r in (header,adapter.physical(row))]}]}]}
        return SimpleNamespace(execute=lambda:data)
    def batch(**kw): calls.append(kw['body']);return SimpleNamespace(execute=lambda:{})
    def patch(**kw): calls.append(kw['body']);return SimpleNamespace(execute=lambda:{'totalUpdatedRows':1})
    g=GoogleRows.__new__(GoogleRows);g.sid='test';g.sheet_id=0
    g.repo=SimpleNamespace(settings=SimpleNamespace(sheet_name='시트1',organization=org))
    g.api=SimpleNamespace(get=get,batchUpdate=batch,values=lambda:SimpleNamespace(batchUpdateByDataFilter=patch))
    assert g.snapshot()[0][1]==row
    g.batch([{'appendCells':{'sheetId':0,'rows':[cells(row)],'fields':'userEnteredValue'}}])
    assert len(calls[-1]['requests'][0]['appendCells']['rows'][0]['values'])==17
    g.patch(1,{2:'ignored',6:5,18:'ignored'})
    assert calls[-1]['data'][0]['values']==[[None,None,None,None,None,5]]

def test_ayf_api_does_not_collect_or_return_removed_fields(tmp_path):
    import uuid
    from backend.config import Settings
    from backend.tests.test_organizations import connect
    cfg=Settings(_env_file=None,organization_id='ayf',app_env='demo',app_base_url='http://testserver',demo_data_path=str(tmp_path/'records.json'))
    c,app,boot=connect(cfg)
    assert boot['organization']['department_enabled'] is False
    assert c.post('/api/analyses',data={'facility':'재단','department':'이전 부서','description':'시험'}).status_code==422
    response=c.post('/api/analyses',data={'facility':'재단','description':'시험 위험'})
    assert response.status_code==200
    body={'request_id':str(uuid.uuid4()),'draft_id':response.json()['draft_id'],'items':[dict(index=0,location='시험',scenario='시험 위험',solution='시험 조치')]}
    assert c.post('/api/assessments',json={**body,'submitter_name':'홍㉠㉢'}).status_code==422
    assert c.post('/api/assessments',json=body).status_code==200
    c.post('/api/auth/demo',data={'role':'admin'})
    result=c.get('/api/assessments').json()['items']
    assert len(result)==1
    assert 'department' not in result[0] and 'submitter_name' not in result[0]
    c.close()
