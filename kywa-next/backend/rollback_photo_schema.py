"""Archive v1.1 extensions before returning one institution to its 17/19-column baseline.

Never restore an old whole-sheet snapshot over newer submissions. Default is dry-run;
the app writer must be paused for apply. Archives remain in the same private file.
"""
import argparse
import copy
import json
from datetime import datetime
from pathlib import Path

from .compact_storage import TAB
from .domain import now
from .migrate_photos import LABEL
from .repository import SheetsRepository,cells
from .sheet_sync import GoogleRows
from .sheet_schema import SheetSchemaError
from .sheet_format import fingerprint

ARCHIVE='rollback-v1.1'


def baseline_value(value):
    if isinstance(value,list):return [baseline_value(v) for v in value]
    if not isinstance(value,dict):return value
    out={k:baseline_value(v) for k,v in value.items() if not k.startswith('_internal')}
    if 'before' in value and 'id' in value:
        for key in ('photo_ids','photo_view_urls','plan'):out.pop(key,None)
        if out.get('status')=='조치예정':out['status']='조치 중' if out.get('after') else '접수'
    for key in ('source_values','observed_values'):
        if key in out:
            out[key]=out[key][:19]
            out['observed_hash' if key=='observed_values' else 'hash']=fingerprint(out[key])
    if 'formats' in out:out['formats']=out['formats'][:19]
    if 'record' in out and 'source_values' not in out:out.pop('hash',None)
    return out


def conversion(entries):
    if any(kind in ('request','edit') and value.get('state') in ('appending','pending')
           for (kind,_),(_,value) in entries.items()):
        raise SheetSchemaError('미완료 저장을 복구한 뒤 버전을 복구하세요.')
    changes=[]
    stamp=now()
    for (kind,key),(_,value) in entries.items():
        if kind==ARCHIVE:continue
        converted=baseline_value(value)
        if converted==value:continue
        archive_key=kind+':'+key
        if (ARCHIVE,archive_key) in entries:
            prior=entries[(ARCHIVE,archive_key)][1]
            if prior.get('original')!=value:
                raise SheetSchemaError('다른 시점의 복구 보관본이 있습니다. 기존 보관본을 덮어쓰지 않습니다.')
        changes.append((ARCHIVE,archive_key,{'source_version':'v1.1.0','archived_at':stamp,'original':copy.deepcopy(value)}))
        changes.append((kind,key,converted))
    return changes


def rollback(settings,apply=False,backup_dir='local-data/version-backups'):
    repo=SheetsRepository(settings);g=GoogleRows(repo)
    rows,ids,notes,_=g.snapshot();entries=g.entries();header=g.layout.header
    result={'organization':settings.organization.id,'records':max(0,len(rows)-1),'columns':len(header),'applied':False}
    if not g.layout.multiple_photos:return {**result,'already_baseline':True}
    if header[-1]!=LABEL or notes:raise SheetSchemaError('추가 사진 열 위치 또는 미완료 제출을 확인하세요.')
    changes=conversion(entries)
    if not apply:return {**result,'target_columns':len(header)-1,'archived_entries':len(changes)//2}
    full=g.api.get(spreadsheetId=g.sid,includeGridData=True).execute()
    folder=Path(backup_dir)/settings.organization.id;folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    path=folder/(stamp+'.json');path.write_text(json.dumps(full,ensure_ascii=False),encoding='utf-8')
    if g.snapshot()[:3]!=(rows,ids,notes):raise SheetSchemaError('복구 준비 중 평가가 변경되었습니다. 다시 점검하세요.')
    g._entries=None
    if g.entries()!=entries:raise SheetSchemaError('복구 준비 중 관리 정보가 변경되었습니다.')
    requests=[];next_id=max(g.ids.values())+1
    for offset,name in enumerate((settings.sheet_name,TAB,settings.history_sheet_name)):
        new_id=next_id+offset
        requests.extend([{'duplicateSheet':{'sourceSheetId':g.ids[name],'newSheetId':new_id,'newSheetName':f'_백업_버전복구_{stamp}_{offset}'}},
            {'updateSheetProperties':{'properties':{'sheetId':new_id,'hidden':True},'fields':'hidden'}}])
    # Archive original history objects carrying internal facts before removing them
    # from the baseline API's direct event serialization.
    history=repo._values(settings.history_sheet_name)
    for index,row in enumerate(history[1:],1):
        if len(row)<7 or not row[6]:continue
        event=json.loads(row[6]);converted=baseline_value(event)
        if converted!=event:
            changes.append((ARCHIVE,'event:'+event['id'],{'source_version':'v1.1.0','archived_at':now(),'original':event}))
            requests.append({'updateCells':{'start':{'sheetId':g.ids[settings.history_sheet_name],'rowIndex':index,'columnIndex':6},
                'rows':[cells([json.dumps(converted,ensure_ascii=False)])],'fields':'userEnteredValue'}})
    requests.append({'deleteDimension':{'range':{'sheetId':g.sheet_id,'dimension':'COLUMNS','startIndex':len(header)-1,'endIndex':len(header)}}})
    # The existing table/filter follows native column deletion. All rows survive.
    g.save(changes,extra=requests)
    after=GoogleRows(repo);values,new_ids,_,_=after.snapshot()
    if (after.layout.header!=header[:-1] or ids!=new_ids
            or [r[:19] for r in values[1:]]!=[r[:19] for r in rows[1:]]):
        raise SheetSchemaError('버전 복구 후 값·행 식별 대조가 다릅니다. 백업을 확인하세요.')
    return {**result,'applied':True,'columns':len(header)-1,'backup':str(path),'archived_entries':sum(k==ARCHIVE for k,_,_ in changes)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--backup-dir',default='local-data/version-backups');a=p.parse_args()
    cfg=__import__('backend.config',fromlist=['Settings']).Settings();cfg.validate_runtime()
    print(json.dumps(rollback(cfg,a.apply,a.backup_dir),ensure_ascii=False))
