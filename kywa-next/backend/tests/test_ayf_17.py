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
