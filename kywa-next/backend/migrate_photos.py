"""Append a second-before-photo column, preserving every existing cell and identity."""
import copy
import json
from datetime import datetime
from pathlib import Path
from .repository import SheetsRepository, cells
from .sheet_sync import GoogleRows, blank
from .visible_layout import VisibleLayout
from .sheet_schema import SheetSchemaError
from .compact_storage import TAB

LABEL='개선 전 사진 2'


def plan(header, org, entries):
    layout=VisibleLayout(header,org)
    if any(kind in ('request','edit') and value.get('state') in ('appending','pending')
           for (kind,_),(_,value) in entries.items()):
        raise SheetSchemaError('미완료 저장 요청을 먼저 복구하세요.')
    if layout.multiple_photos:
        if header[-1]!=LABEL: raise SheetSchemaError('두 번째 사진 열은 평가표 오른쪽 끝에 있어야 합니다.')
        return list(header)
    return list(header)+[LABEL]


def migrate(settings, apply=False, backup_dir='local-data/photo-schema-backups'):
    repo=SheetsRepository(settings);g=GoogleRows(repo)
    rows,identities,notes,_=g.snapshot();entries=g.entries();header=g.layout.header
    target=plan(header,settings.organization,entries)
    result={'organization':settings.organization.id,'old_columns':len(header),'new_columns':len(target),
            'records':sum(not blank(r) for r in rows[1:]),'applied':False}
    if target==header: return {**result,'already_applied':True}
    if notes: raise SheetSchemaError('미완료 제출 메모를 먼저 복구하세요.')
    if not apply:return result
    snapshot=g.api.get(spreadsheetId=g.sid,includeGridData=True).execute()
    sheet=next(s for s in snapshot['sheets'] if s['properties']['sheetId']==g.sheet_id)
    for block in sheet.get('data',[]):
        for row in block.get('rowData',[]):
            if any(cell.get('userEnteredValue') for cell in row.get('values',[])[len(header):]):
                raise SheetSchemaError('추가 사진 열 위치에 기존 값이 있습니다. 확장을 중단합니다.')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f');folder=Path(backup_dir)/settings.organization.id
    folder.mkdir(parents=True,exist_ok=True);backup=folder/(stamp+'.json')
    backup.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')
    if g.snapshot()[:3]!=(rows,identities,notes):raise SheetSchemaError('백업 중 평가가 변경되었습니다. 다시 확인하세요.')
    g._entries=None
    if g.entries()!=entries:raise SheetSchemaError('백업 중 관리 기록이 변경되었습니다. 다시 확인하세요.')
    requests=[];next_id=max(g.ids.values())+1
    for offset,name in enumerate((settings.sheet_name,TAB,settings.history_sheet_name)):
        if name not in g.ids:raise SheetSchemaError('백업할 관리 탭을 찾을 수 없습니다.')
        new_id=next_id+offset
        requests += [{'duplicateSheet':{'sourceSheetId':g.ids[name],'newSheetId':new_id,'newSheetName':f'_백업_사진2_{stamp}_{offset}'}},
                     {'updateSheetProperties':{'properties':{'sheetId':new_id,'hidden':True},'fields':'hidden'}}]
    count=sheet['properties']['gridProperties']['columnCount']
    if count<len(target):requests.append({'appendDimension':{'sheetId':g.sheet_id,'dimension':'COLUMNS','length':len(target)-count}})
    row_count=sheet['properties']['gridProperties']['rowCount'];primary=g.layout.positions[12]
    requests += [
        {'copyPaste':{'source':{'sheetId':g.sheet_id,'startColumnIndex':primary,'endColumnIndex':primary+1,'startRowIndex':0,'endRowIndex':row_count},
                      'destination':{'sheetId':g.sheet_id,'startColumnIndex':len(header),'endColumnIndex':len(target),'startRowIndex':0,'endRowIndex':row_count},'pasteType':'PASTE_FORMAT'}},
        {'repeatCell':{'range':{'sheetId':g.sheet_id,'startColumnIndex':len(header),'endColumnIndex':len(target)},'cell':{'userEnteredFormat':{'textFormat':{}}},'fields':'userEnteredFormat.textFormat.link'}},
        {'updateCells':{'start':{'sheetId':g.sheet_id,'rowIndex':0,'columnIndex':len(header)},'rows':[cells([LABEL])],'fields':'userEnteredValue'}}]
    for table in sheet.get('tables',[]):
        rng=table['range']
        if rng.get('startColumnIndex',0)==0 and rng['endColumnIndex']==len(header):
            cols=copy.deepcopy(table.get('columnProperties',[]))
            if cols:cols.append({'columnIndex':len(header),'columnName':LABEL})
            requests.append({'updateTable':{'table':{'tableId':table['tableId'],'range':{**rng,'endColumnIndex':len(target)},**({'columnProperties':cols} if cols else {})},'fields':'range'+(',columnProperties' if cols else '')}})
    # Native tables own their filter. Reapplying a range filter over a table is
    # rejected by Sheets, even if a historical basicFilter exists in the response.
    if sheet.get('basicFilter') and not sheet.get('tables'):
        requests.append({'setBasicFilter':{'filter':{**sheet['basicFilter'],'range':{**sheet['basicFilter']['range'],'endColumnIndex':len(target)}}}})
    # One atomic update: snapshots plus the new rightmost column. No original value is rewritten.
    g.api.batchUpdate(spreadsheetId=g.sid,body={'requests':requests}).execute()
    after=GoogleRows(repo);values,ids,_,_=after.snapshot()
    if after.layout.header!=target or ids!=identities or [r[:19] for r in values[1:]]!=[r[:19] for r in rows[1:]]:
        raise SheetSchemaError('추가 사진 열 검증이 다릅니다. 백업을 확인하고 쓰기를 재개하지 마세요.')
    return {**result,'applied':True,'backup':str(backup)}


if __name__=='__main__':
    import argparse
    from .config import Settings
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--backup-dir',default='local-data/photo-schema-backups')
    args=parser.parse_args();cfg=Settings();cfg.validate_runtime()
    print(json.dumps(migrate(cfg,args.apply,args.backup_dir),ensure_ascii=False))
