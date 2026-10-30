"""KYWA-only, backed-up, atomic column migration. Other institutions are rejected."""
import argparse
from datetime import datetime
import json
import uuid
from .config import ROOT
from .repository import SheetsRepository, google_client, cells, quoted
from .sheet_schema import SheetSchemaError
from .domain import HEADERS, digest
from .compact_storage import TAB, HEAD, VISIBLE, compact, clean, padded, packed, META_COLUMNS


def migrate(settings, apply=False):
    if settings.organization.id!='kywa': raise ValueError('KYWA에서만 실행할 수 있습니다.')
    repo=SheetsRepository(settings); svc=google_client(settings,'sheets','v4').spreadsheets()
    sid=settings.spreadsheet_id
    rows=repo._rows()
    if compact(rows[0]):
        records=repo.records()
        return {'already_applied':True,'records':len(records)}
    if rows[0] != HEADERS+['제출자 성명']:
        raise SheetSchemaError('기존 KYWA 24개 헤더가 예상과 다릅니다. 자동 변경하지 않습니다.')
    if any(any(str(v).strip() for v in row[24:]) for row in rows):
        raise SheetSchemaError('예상 열 밖에 값이 있어 중단합니다.')
    records=repo._decoded(rows); before_events=repo.events()
    result={'records':len(records),'events':len(before_events),'removed':['평가ID','평가기준버전','수정버전','시스템데이터'],'applied':False}
    if not apply: return result
    # Include all grids (values, formulas, formats, notes), dimensions and history.
    snapshot=svc.get(spreadsheetId=sid,includeGridData=True).execute()
    props={s['properties']['title']:s['properties'] for s in snapshot['sheets']}
    if TAB in props: raise SheetSchemaError('기존 숨김 관리 탭이 있어 자동 덮어쓰지 않습니다.')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    folder=ROOT/'local-data/migration-backups'; folder.mkdir(parents=True,exist_ok=True)
    backup=folder/('kywa-compact-'+stamp+'.json')
    backup.write_text(json.dumps({'spreadsheet_id':sid,'snapshot':snapshot,'values':rows,'events':before_events},ensure_ascii=False),encoding='utf-8')
    # A cloud copy of the exact tab also preserves formatting and makes recovery simple.
    old_id=props[settings.sheet_name]['sheetId']; new_id=max(p['sheetId'] for p in props.values())+1
    backup_title='_백업_KYWA_'+stamp
    svc.batchUpdate(spreadsheetId=sid,body={'requests':[{'duplicateSheet':{'sourceSheetId':old_id,'newSheetId':new_id,'newSheetName':backup_title}},
        {'updateSheetProperties':{'properties':{'sheetId':new_id,'hidden':True},'fields':'hidden'}}]}).execute()
    fresh=repo._rows()
    # Streamlit appends are safe; concurrent changes to previously inspected rows are not.
    if fresh[:len(rows)]!=rows: raise SheetSchemaError('백업 중 평가 값이 바뀌었습니다. 이관을 중단합니다.')
    rows=fresh; records=repo._decoded(rows)
    latest=folder/('kywa-compact-'+stamp+'-latest-values.json')
    latest.write_text(json.dumps({'values':rows,'events':repo.events()},ensure_ascii=False),encoding='utf-8')
    converted=[padded(row[:18]+[row[20] if len(row)>20 else '',row[23] if len(row)>23 else '']) for row in rows[1:]]
    hidden=[cells(HEAD)]
    for record in records:
        index=record['_sheet_row']
        value={'row':index,'hash':digest(converted[index-1]),'record':clean(record)}
        hidden.append(cells(packed('record',record['id'],value)))
    managed_id=new_id+1
    requests=[{'addSheet':{'properties':{'sheetId':managed_id,'title':TAB,'hidden':True,'gridProperties':{'rowCount':max(1000,len(hidden)+100),'columnCount':META_COLUMNS}}}},
        {'updateCells':{'start':{'sheetId':managed_id,'rowIndex':0,'columnIndex':0},'rows':hidden,'fields':'userEnteredValue'}},
        {'deleteDimension':{'range':{'sheetId':old_id,'dimension':'COLUMNS','startIndex':21,'endIndex':23}}},
        {'deleteDimension':{'range':{'sheetId':old_id,'dimension':'COLUMNS','startIndex':18,'endIndex':20}}}]
    if len(rows)>1:
        requests.append({'copyPaste':{'source':{'sheetId':old_id,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':20},
            'destination':{'sheetId':old_id,'startRowIndex':1,'endRowIndex':len(rows),'startColumnIndex':0,'endColumnIndex':20},'pasteType':'PASTE_FORMAT'}})
        requests.append({'repeatCell':{'range':{'sheetId':old_id,'startRowIndex':1,'endRowIndex':len(rows),'startColumnIndex':0,'endColumnIndex':20},
            'cell':{'userEnteredFormat':{'textFormat':{'fontFamily':'Roboto','fontSize':10}}},'fields':'userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize'}})
    # All structural changes and metadata insertion are one atomic Sheets request.
    svc.batchUpdate(spreadsheetId=sid,body={'requests':requests}).execute()
    after_rows=repo._rows(); after=repo.records()
    if after_rows[0]!=VISIBLE or [padded(r) for r in after_rows[1:len(rows)]]!=converted:
        raise SheetSchemaError('이관 후 평가 값을 확인해야 합니다. 백업이 보관되어 있습니다.')
    expected={r['id']:clean(r) for r in records}; actual={r['id']:clean(r) for r in after}
    if any(actual.get(k)!=v for k,v in expected.items()) or repo.events()!=before_events:
        raise SheetSchemaError('평가·조치 연결 대조가 일치하지 않습니다. 백업을 확인하세요.')
    return {**result,'records':len(records),'applied':True,'backup':str(backup),'cloud_backup':backup_title}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--apply',action='store_true'); args=parser.parse_args()
    from .check_connections import target_settings
    print(json.dumps(migrate(target_settings('kywa'),args.apply),ensure_ascii=False,indent=2))
