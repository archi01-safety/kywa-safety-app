"""Backed-up AYF 19 -> 17 column migration; run with application writes paused."""
import copy
import json
from datetime import datetime
from pathlib import Path

from .repository import SheetsRepository, google_client, cells
from .sheet_sync import GoogleRows, fingerprint, blank
from .compact_storage import TAB, packed
from .visible_layout import VisibleLayout
from .sheet_schema import SheetSchemaError


def plan(header, org, entries):
    if org.id != 'ayf' or org.department_enabled or org.submitter_name.mode != 'disabled':
        raise SheetSchemaError('AYF 시설 중심 설정에서만 전환할 수 있습니다.')
    adapter = VisibleLayout(header, org)
    if len(header) == 17:
        return [], []
    if any(v.get('state') == 'appending' for (kind, _), (_, v) in entries.items() if kind == 'request'):
        raise SheetSchemaError('진행 중인 제출을 복구한 뒤 이관하세요.')
    removed = sorted([adapter.positions[2], adapter.positions[18]], reverse=True)
    changes = []
    for (kind, key), (index, original) in entries.items():
        if kind != 'record' or original.get('deleted'):
            continue
        value = copy.deepcopy(original)
        if 'source_values' in value:
            value['source_values'][2] = value['source_values'][18] = ''
            value['hash'] = fingerprint(value['source_values'])
        value['record']['department'] = value['record']['submitter_name'] = ''
        value['record'].pop('legacy_values', None)
        changes.append((index, cells(packed(kind, key, value, True))))
    return removed, changes


def migrate(settings, apply=False, backup_dir='local-data/ayf-17-backups'):
    repo = SheetsRepository(settings)
    g = GoogleRows(repo)
    rows, identities, notes, _ = g.snapshot()
    entries = g.entries()
    header = g.layout.header
    removed, changes = plan(header, settings.organization, entries)
    result = dict(old_columns=len(header), new_columns=17, records=sum(not blank(r) for r in rows[1:]), applied=False)
    if not removed:
        return {**result, 'already_applied': True}
    if notes:
        raise SheetSchemaError('미완료 제출 메모가 있습니다. 먼저 제출을 복구하세요.')
    if not apply:
        return result
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder = Path(backup_dir); folder.mkdir(parents=True, exist_ok=True)
    snapshot = g.api.get(spreadsheetId=g.sid, includeGridData=True).execute()
    (folder/(stamp+'.json')).write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
    fresh, current_ids, current_notes, _ = g.snapshot()
    g._entries = None
    if fresh != rows or current_ids != identities or current_notes != notes or g.entries() != entries:
        raise SheetSchemaError('백업 중 데이터가 바뀌었습니다. 쓰기를 중지한 뒤 다시 실행하세요.')
    backup_id = max(g.ids.values())+1
    requests = [
        {'duplicateSheet': {'sourceSheetId': g.sheet_id, 'newSheetId': backup_id, 'newSheetName': '_백업_AYF17_'+stamp}},
        {'updateSheetProperties': {'properties': {'sheetId': backup_id, 'hidden': True}, 'fields': 'hidden'}}]
    requests += [{'updateCells': {'start': {'sheetId': g.ids[TAB], 'rowIndex': index, 'columnIndex': 0},
                  'rows': [row], 'fields': 'userEnteredValue'}} for index, row in changes]
    requests += [{'deleteDimension': {'range': {'sheetId': g.sheet_id, 'dimension': 'COLUMNS',
                  'startIndex': col, 'endIndex': col+1}}} for col in removed]
    # Column deletion carries table columns, formats and row identities with it.
    g.api.batchUpdate(spreadsheetId=g.sid, body={'requests': requests}).execute()
    after = GoogleRows(repo)
    values, ids, _, _ = after.snapshot()
    expected = copy.deepcopy(rows)
    for row in expected[1:]: row[2] = row[18] = ''
    if len(after.layout.header) != 17 or values != expected or ids != identities:
        raise SheetSchemaError('이관 후 값 또는 행 연결 대조가 다릅니다. 백업을 확인하세요.')
    return {**result, 'applied': True, 'backup': str(folder/(stamp+'.json'))}
