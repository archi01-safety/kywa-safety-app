"""Explicit, backed-up partner migration. Read-only unless apply=True.

Run on a verified copy first, with the partner app writer paused. Original
Streamlit columns retain their positions. No production KYWA mutation allowed.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

from .compact_storage import TAB, HEAD, META_COLUMNS, packed, clean
from .domain import HEADERS, HISTORY_HEADERS
from .repository import SheetsRepository, google_client, cells
from .sheet_schema import Layout, SheetSchemaError
from .sheet_format import canonical, fingerprint, format_requests, DATE_FORMAT
from .sheet_sync import prepare
from .visible_layout import VisibleLayout, MANAGEMENT_KEYS, is_visible

PARTNERS = {'ayf','fowi','knps','knf','kohi','khidi','cayf'}


def migrate(settings, apply=False, backup_dir='local-data/partner-backups'):
    org = settings.organization
    if org.id not in PARTNERS or not org.enhanced:
        raise ValueError('승인된 지원기관의 개선 버전에서만 실행할 수 있습니다.')
    repo = SheetsRepository(settings)
    svc = google_client(settings,'sheets','v4').spreadsheets()
    sid = settings.spreadsheet_id
    rows = repo._values(settings.sheet_name, raw=True)
    if rows and is_visible(rows[0],org):
        # Idempotent continuation after the atomic schema change.
        return {'already_applied':True, **prepare(repo,apply=apply)}
    header = rows[0] if rows else []
    layout = Layout(header,org) if header else None
    if not header and org.id != 'ayf':
        raise SheetSchemaError('기존 기관 평가표가 비어 있습니다. 자동 초기화하지 않습니다.')
    removed = sorted(layout.columns[k] for k in MANAGEMENT_KEYS) if layout else []
    target = [h for i,h in enumerate(header) if i not in removed] if header else HEADERS[:18]+['제출자 성명']
    adapter = VisibleLayout(target,org)
    if any(any(str(v).strip() for v in row[len(header):]) for row in rows):
        raise SheetSchemaError('예상 열 밖에 데이터가 있어 이관을 중단합니다.')
    records = repo._decoded(repo._rows()) if rows else []
    info = svc.get(spreadsheetId=sid,fields='sheets.properties').execute()
    ids = {x['properties']['title']:x['properties']['sheetId'] for x in info['sheets']}
    if TAB in ids:
        raise SheetSchemaError('미이관 평가표에 숨김 관리 탭이 있습니다. 복구 상태를 먼저 확인하세요.')
    events = repo.events() if settings.history_sheet_name in ids else []
    result = {'organization':org.id,'records':len(records),'events':len(events),
              'old_columns':len(header),'new_columns':19,'removed_columns':removed,'applied':False}
    if not apply: return result
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    folder = Path(backup_dir)/org.id; folder.mkdir(parents=True,exist_ok=True)
    full = svc.get(spreadsheetId=sid,includeGridData=True).execute()
    (folder/(stamp+'.json')).write_text(json.dumps({'spreadsheet_id':sid,'snapshot':full,'values':rows,'events':events},ensure_ascii=False),encoding='utf-8')
    sheet_id = ids[settings.sheet_name]
    new_id = max(ids.values())+1
    backup_title = '_백업_'+org.short_name+'_'+stamp
    svc.batchUpdate(spreadsheetId=sid,body={'requests':[
        {'duplicateSheet':{'sourceSheetId':sheet_id,'newSheetId':new_id,'newSheetName':backup_title}},
        {'updateSheetProperties':{'properties':{'sheetId':new_id,'hidden':True},'fields':'hidden'}}]}).execute()
    fresh = repo._values(settings.sheet_name,raw=True)
    if fresh != rows or (events and repo.events()!=events):
        raise SheetSchemaError('백업 중 평가 또는 이력이 바뀌었습니다. 새 백업으로 다시 실행하세요.')
    converted = [adapter.canonical([v for i,v in enumerate(row) if i not in removed]) for row in rows[1:]]
    converted = [canonical(row) if any(str(v).strip() for v in row) else ['']*19 for row in converted]
    hidden = [cells(HEAD)]
    for record in records:
        index = record['_sheet_row']; source = converted[index-1]
        hidden.append(cells(packed('record',record['id'],{'row':index,'hash':fingerprint(source),
            'source_values':source,'record':clean(record),'migration_position_verified':True})))
    requests = [{'addSheet':{'properties':{'sheetId':new_id+1,'title':TAB,'hidden':True,
        'gridProperties':{'rowCount':max(1000,len(hidden)+100),'columnCount':META_COLUMNS}}}},
        {'updateCells':{'start':{'sheetId':new_id+1,'rowIndex':0,'columnIndex':0},'rows':hidden,'fields':'userEnteredValue'}}]
    if settings.history_sheet_name not in ids:
        requests += [{'addSheet':{'properties':{'sheetId':new_id+2,'title':settings.history_sheet_name}}},
            {'updateCells':{'start':{'sheetId':new_id+2,'rowIndex':0,'columnIndex':0},'rows':[cells(HISTORY_HEADERS)],'fields':'userEnteredValue'}}]
    for col in reversed(removed):
        requests.append({'deleteDimension':{'range':{'sheetId':sheet_id,'dimension':'COLUMNS','startIndex':col,'endIndex':col+1}}})
    requests += [{'updateSpreadsheetProperties':{'properties':{'timeZone':'Asia/Seoul','locale':'ko_KR'},'fields':'timeZone,locale'}}]
    if not header:
        requests += [{'updateCells':{'start':{'sheetId':sheet_id,'rowIndex':0,'columnIndex':0},'rows':[cells(target)],'fields':'userEnteredValue'}},
            {'updateSheetProperties':{'properties':{'sheetId':sheet_id,'gridProperties':{'frozenRowCount':1}},'fields':'gridProperties.frozenRowCount'}},
            {'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':19},
                'cell':{'userEnteredFormat':{'textFormat':{'fontFamily':'Roboto','fontSize':10},'wrapStrategy':'WRAP','verticalAlignment':'MIDDLE'}},'fields':'userEnteredFormat'}},
            {'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':1},
                'cell':{'userEnteredFormat':{'numberFormat':{'type':'DATE_TIME','pattern':DATE_FORMAT}}},'fields':'userEnteredFormat.numberFormat'}},
            {'addTable':{'table':{'name':'Form_Responses','range':{'sheetId':sheet_id,'startRowIndex':0,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':19}}}}]
    if converted:
        requests.append({'updateCells':{'start':{'sheetId':sheet_id,'rowIndex':1,'columnIndex':0},'rows':[cells([r[0]]) for r in converted],'fields':'userEnteredValue'}})
        requests.extend(format_requests(svc,sid,settings.sheet_name,1,len(rows),19))
    svc.batchUpdate(spreadsheetId=sid,body={'requests':requests}).execute()
    after = repo._values(settings.sheet_name,raw=True)
    if after[0]!=target or [canonical(adapter.canonical(r)) for r in after[1:len(rows)]] != converted:
        raise SheetSchemaError('이관 후 값 대조가 다릅니다. 백업으로 복구해야 합니다.')
    linked = prepare(repo,apply=True)
    def preserved(record):
        value=clean(record);value.pop('legacy_values',None);return value
    current = {r['id']:preserved(r) for r in repo.records()}
    if any(current.get(r['id']) != preserved(r) for r in records) or repo.events()!=events:
        raise SheetSchemaError('기존 평가 또는 조치이력 대조가 다릅니다. 쓰기를 재개하지 마세요.')
    return {**result,'applied':True,'identity':linked,'backup':str(folder/(stamp+'.json')),'cloud_backup':backup_title}
