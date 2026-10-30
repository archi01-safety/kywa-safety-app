"""KYWA visible 20-column sheet + hidden metadata and recoverable append journal."""
import copy
import json
import re
from .domain import HEADERS, HISTORY_HEADERS, digest, sheet_row
from .sheet_schema import Layout, SheetSchemaError
from .submitter_name import display_name

TAB = '_시스템관리'
HEAD = ['종류', '키', '내용']
META_COLUMNS = 64

def packed(kind, key, value, clear=False):
    # Google Sheets limits each cell to 50,000 characters. Split large journals.
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    parts = [raw[i:i+20000] for i in range(0, len(raw), 20000)]
    if len(parts) > META_COLUMNS-2:
        raise SheetSchemaError('관리 정보가 저장 한도를 초과했습니다. 평가를 나누어 제출해 주세요.')
    row = [kind, key, *parts]
    return row + [''] * (META_COLUMNS-len(row)) if clear else row

VISIBLE = HEADERS[:18] + ['처리상태', '제출자 성명']


def compact(header):
    return list(header) == VISIBLE


def clean(record):
    value = copy.deepcopy(record)
    for key in list(value):
        if key.startswith('_sheet_'):
            value.pop(key)
    value['submitter_name'] = display_name(value.get('submitter_name'))
    return value


def padded(row):
    return list(row[:20]) + [''] * max(0, 20-len(row))


def visible(record):
    row = sheet_row(clean(record), True)
    # Keep the original sheet's familiar timestamp rendering for new entries.
    if not record.get('legacy_values'):
        from datetime import datetime
        row[0] = datetime.fromisoformat(record['created_at']).strftime('%Y-%m-%d %H:%M:%S')
    return row[:18] + [record['status'], display_name(record.get('submitter_name'))]


def metadata(repo):
    rows = repo._values(TAB)
    if not rows or rows[0] != HEAD:
        raise SheetSchemaError('숨김 관리 탭을 준비하거나 백업을 복구해 주세요.')
    result = {}
    for index, row in enumerate(rows[1:], 1):
        if not any(row):
            continue
        if len(row) < 3 or (row[0], row[1]) in result:
            raise SheetSchemaError('숨김 관리 정보가 중복되거나 손상되었습니다.')
        result[(row[0], row[1])] = (index, json.loads(''.join(row[2:])))
    return result


def decode(repo, rows, entries=None):
    entries = metadata(repo) if entries is None else entries
    mapped = {}
    for (kind, key), (_, value) in entries.items():
        if kind != 'record':
            continue
        index = value['row']
        if index in mapped or index >= len(rows) or digest(padded(rows[index])) != value['hash']:
            raise SheetSchemaError('평가 행이 이동하거나 변경되었습니다. 원본과 관리 정보를 확인하세요.')
        mapped[index] = value['record']
    layout = Layout(VISIBLE, repo.settings.organization)
    identity = repo.settings.spreadsheet_id + ':' + repo.settings.sheet_name
    records = []
    for index, row in enumerate(rows[1:], 1):
        if not any(str(v).strip() for v in row):
            continue
        record = copy.deepcopy(mapped.get(index))
        if record is None:
            record = layout.legacy(row, index, identity)
            record['status'] = row[18] if len(row)>18 and row[18] else record['status']
        record.update(_sheet_row=index, _sheet_hash=digest(padded(row)), _sheet_revision=record['revision'])
        records.append(record)
    if len({r['id'] for r in records}) != len(records):
        raise SheetSchemaError('중복된 평가 ID입니다.')
    return records


def recover(repo, rows):
    """Finish an acknowledged-or-lost append before looking for replayed requests.

    Never append from recovery. Zero or multiple matches are left unresolved;
    this deliberately favors a visible retry error over a duplicate submission.
    """
    from .repository import google_client, cells
    entries = metadata(repo)
    pending = [(key, index, value) for (kind, key), (index, value) in entries.items()
               if kind == 'request' and value.get('state') == 'appending']
    if not pending:
        return entries
    svc = google_client(repo.settings, 'sheets', 'v4').spreadsheets()
    props = svc.get(spreadsheetId=repo.settings.spreadsheet_id, fields='sheets.properties').execute()
    ids = {s['properties']['title']:s['properties']['sheetId'] for s in props['sheets']}
    occupied = {v['row'] for (kind,_),(_,v) in entries.items() if kind == 'record'}
    requests = []
    for key, index, journal in pending:
        expected = journal['rows']
        matches = [i for i in range(journal['start'], len(rows)-len(expected)+1)
                   if not occupied.intersection(range(i,i+len(expected)))
                   and [padded(r) for r in rows[i:i+len(expected)]] == expected]
        if len(matches) != 1:
            continue
        start = matches[0]
        journal = {**journal, 'state':'committed', 'row':start}
        requests.append({'updateCells':{'start':{'sheetId':ids[TAB],'rowIndex':index,'columnIndex':0},
            'rows':[cells(packed('request',key,journal,True))],'fields':'userEnteredValue'}})
        for offset, record in enumerate(journal['records']):
            value = {'row':start+offset,'hash':digest(expected[offset]),'record':record}
            requests.append({'appendCells':{'sheetId':ids[TAB],
                'rows':[cells(packed('record',record['id'],value))],'fields':'userEnteredValue'}})
        requests.append({'copyPaste':{'source':{'sheetId':ids[repo.settings.sheet_name],'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':20},
            'destination':{'sheetId':ids[repo.settings.sheet_name],'startRowIndex':start,'endRowIndex':start+len(expected),'startColumnIndex':0,'endColumnIndex':20},'pasteType':'PASTE_FORMAT'}})
        occupied.update(range(start,start+len(expected)))
    if requests:
        svc.batchUpdate(spreadsheetId=repo.settings.spreadsheet_id,body={'requests':requests}).execute()
        return metadata(repo)
    return entries


def apply(repo, records, events):
    from .repository import google_client, quoted, cells, RepositoryError
    svc = google_client(repo.settings, 'sheets', 'v4').spreadsheets()
    sid = repo.settings.spreadsheet_id
    info = svc.get(spreadsheetId=sid, fields='sheets.properties').execute()
    ids = {s['properties']['title']:s['properties']['sheetId'] for s in info['sheets']}
    entries = metadata(repo)
    rows = repo._rows()
    current = {r['id']:r for r in decode(repo, rows, entries)}
    def save_entries(changes, extra=None):
        requests = list(extra or [])
        appended = []
        for kind,key,value in changes:
            row = cells(packed(kind,key,value,(kind,key) in entries))
            if (kind,key) in entries:
                requests.append({'updateCells':{'start':{'sheetId':ids[TAB],'rowIndex':entries[(kind,key)][0],'columnIndex':0},'rows':[row],'fields':'userEnteredValue'}})
            else:
                appended.append(row)
        if appended:
            requests.append({'appendCells':{'sheetId':ids[TAB],'rows':appended,'fields':'userEnteredValue'}})
        if requests:
            svc.batchUpdate(spreadsheetId=sid, body={'requests':requests}).execute()

    fresh = [r for r in records if '_sheet_row' not in r]
    if fresh and len(fresh) != len(records):
        raise RepositoryError('신규 저장과 기존 수정을 분리해 주세요.')
    changes, requests = [], []
    if fresh:
        operation = fresh[0]['operation_id']
        if any(r['operation_id'] != operation for r in fresh):
            raise RepositoryError('다른 제출 요청이 섞였습니다.')
        expected = [visible(r) for r in fresh]
        payload_hash = digest([[r['id'],r['submit_hash'],r['submit_owner']] for r in fresh])
        pending = entries.get(('request',operation))
        if pending:
            journal = pending[1]
            if journal['hash'] != payload_hash:
                raise RepositoryError('같은 요청번호의 내용이 다릅니다.')
            fresh = journal['records']
            expected = journal['rows']
            matches = [i for i in range(journal['start'],len(rows)-len(expected)+1)
                       if [padded(r) for r in rows[i:i+len(expected)]] == expected]
            if len(matches) != 1:
                raise RepositoryError('이전 제출의 저장 위치를 확인 중입니다. 중복 전송하지 말고 관리자에게 확인해 주세요.')
            start = matches[0]
        else:
            journal = {'hash':payload_hash,'start':len(rows),'rows':expected,'records':[clean(r) for r in fresh],'state':'appending'}
            save_entries([('request',operation,journal)])
            entries = metadata(repo)
            response = svc.values().append(spreadsheetId=sid,range=quoted(repo.settings.sheet_name)+'!A:T',
                valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':expected}).execute()
            match = re.search(r'!A(\d+):T(\d+)$',response['updates']['updatedRange'])
            if not match or int(match[2])-int(match[1])+1 != len(fresh):
                raise RepositoryError('저장 위치 확인에 실패했습니다. 다시 전송하면 기존 결과부터 확인합니다.')
            start = int(match[1])-1
        rows = repo._rows()
        if [padded(r) for r in rows[start:start+len(expected)]] != expected:
            raise RepositoryError('저장한 행의 내용이 달라졌습니다.')
        for offset,record in enumerate(fresh):
            changes.append(('record',record['id'],{'row':start+offset,'hash':digest(expected[offset]),'record':clean(record)}))
        journal['state']='committed'; journal['row']=start
        changes.append(('request',operation,journal))
        # Copy the approved column-by-column format, never neighboring user data.
        requests.append({'copyPaste':{'source':{'sheetId':ids[repo.settings.sheet_name],'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':20},
            'destination':{'sheetId':ids[repo.settings.sheet_name],'startRowIndex':start,'endRowIndex':start+len(fresh),'startColumnIndex':0,'endColumnIndex':20},'pasteType':'PASTE_FORMAT'}})
    else:
        for record in records:
            previous = current.get(record['id'])
            if not previous or any(previous[k] != record[k] for k in ('_sheet_row','_sheet_hash','_sheet_revision')):
                raise RepositoryError('다른 담당자가 변경했습니다. 새로고침하세요.')
            index=previous['_sheet_row']; values=visible(record)
            # Preserve A:M and the originally entered name, including legacy raw names.
            updated=padded(rows[index]); updated[13:19]=values[13:19]
            requests.append({'updateCells':{'start':{'sheetId':ids[repo.settings.sheet_name],'rowIndex':index,'columnIndex':13},'rows':[cells(updated[13:19])],'fields':'userEnteredValue'}})
            changes.append(('record',record['id'],{'row':index,'hash':digest(updated),'record':clean(record)}))
    if events:
        history=repo._values(repo.settings.history_sheet_name)
        if not history or history[0] != HISTORY_HEADERS:
            raise RepositoryError('조치이력 탭을 확인하세요.')
        event_rows=[cells([e['id'],e['record_id'],e['at'],e['actor'],e['kind'],e.get('text',''),json.dumps(e,ensure_ascii=False)]) for e in events]
        requests.append({'appendCells':{'sheetId':ids[repo.settings.history_sheet_name],'rows':event_rows,'fields':'userEnteredValue'}})
    save_entries(changes,requests)
