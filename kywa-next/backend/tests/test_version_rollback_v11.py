import copy
import pytest
from backend.rollback_photo_schema import conversion,baseline_value,ARCHIVE
from backend.sheet_format import fingerprint
from backend.sheet_schema import SheetSchemaError
from backend.tests.test_institutions import current_record
from backend.organization import load_organization
from backend.sheet_sync import visible


def test_downgrade_archives_new_fields_and_keeps_every_newer_record_and_receipt():
    record=current_record(load_organization('kywa'));record.update(photo_ids=['one','two'],photo_id='one',photo_view_urls=['url1','url2'],
        status='조치예정',plan={'text':'조치 예정','due_date':'2026-12-01'},revision=7)
    record['before']['_internal_risk']={'score':300,'version':'private'}
    row=visible(record);row[19]='second-link'
    value={'record':record,'row':12,'metadata_id':99,'source_values':row,'hash':'v11-hash'}
    receipt={'version':2,'state':'committed','records':[record]}
    entries={('record',record['id']):(2,value),('request','request'):(3,receipt)}
    original=copy.deepcopy(entries);changes=conversion(entries)
    assert entries==original
    output={(k,key):v for k,key,v in changes}
    restored=output[('record',record['id'])]
    assert restored['record']['id']==record['id'] and restored['record']['revision']==7
    assert restored['record']['status']=='접수' and 'plan' not in restored['record']
    assert restored['hash']==fingerprint(row[:19]) and len(restored['source_values'])==19
    assert '_internal_risk' not in restored['record']['before']
    assert output[(ARCHIVE,'record:'+record['id'])]['original']==value
    assert output[(ARCHIVE,'request:request')]['original']==receipt
    assert output[('request','request')]['records'][0]['id']==record['id']
    committed={key:(index+1,value) for index,(key,value) in enumerate(output.items())}
    assert conversion(committed)==[]


def test_pending_writes_stop_downgrade_and_history_internal_facts_are_removed():
    with pytest.raises(SheetSchemaError):conversion({('edit','test'):(1,{'state':'pending'})})
    event={'id':'test','text':'원문 보존','after':{'score':4,'_internal_risk':{'score':99}}}
    assert baseline_value(event)=={'id':'test','text':'원문 보존','after':{'score':4}}
