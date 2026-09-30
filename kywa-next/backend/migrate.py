"""Explicit, backup-first migration. Default is read-only. Never invoked by the web server."""
import argparse
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

from .config import Settings, ROOT
from .domain import HEADERS, HISTORY_HEADERS, FACILITIES, digest, now
from .repository import google_client, quoted, cells


def drive_id(value):
    parsed = urlparse(str(value))
    if parsed.hostname not in {'drive.google.com', 'docs.google.com'}:
        return ''
    match = re.search(r'/d/([A-Za-z0-9_-]+)', parsed.path)
    value = match.group(1) if match else parse_qs(parsed.query).get('id', [''])[0]
    return value if re.fullmatch(r'[A-Za-z0-9_-]+', value) else ''


def timestamp(value):
    value = str(value).strip()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        match = re.fullmatch(r'(\d{4})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})\.?\s+(?:(오전|오후)\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?', value)
        if not match:
            raise ValueError('날짜 형식을 확인할 수 없습니다. 원본 사본의 날짜를 먼저 정리하세요.')
        year, month, day, ampm, hour, minute, second = match.groups()
        hour = int(hour)
        if ampm: hour = hour % 12 + (12 if ampm == '오후' else 0)
        parsed = datetime(int(year), int(month), int(day), hour, int(minute), int(second or 0))
    return (parsed.replace(tzinfo=ZoneInfo('Asia/Seoul')) if parsed.tzinfo is None else parsed).isoformat(timespec='seconds')


def integer(value, low, high):
    number = float(value)
    if not number.is_integer() or not low <= number <= high:
        raise ValueError('기존 빈도·강도·점수 범위를 확인하세요.')
    return int(number)


def legacy_record(row, identity):
    row = list(row[:18]) + [''] * max(0, 18-len(row))
    if row[1] not in FACILITIES:
        raise ValueError('기존 시설명을 표준 시설명으로 확인하세요.')
    before = dict(location=str(row[3]), category=str(row[4]), scenario=str(row[5]), p=integer(row[6], 1, 5),
                  s=integer(row[7], 1, 4), score=integer(row[8], 1, 20), grade=str(row[9]),
                  solution=str(row[10]), law=str(row[11]))
    if not before['grade']:
        raise ValueError('기존 위험등급이 비어 있습니다.')
    after = None
    if any(str(v).strip() for v in row[13:17]):
        after = dict(p=integer(row[13], 1, 5), s=integer(row[14], 1, 4), score=integer(row[15], 1, 20),
                     grade=str(row[16]), photo_id=drive_id(row[17]), text='기존 기록에 조치내용 없음',
                     actor='', created_at='', policy='LEGACY-UNKNOWN')
        if not after['grade']: raise ValueError('개선 후 위험등급이 비어 있습니다.')
    return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), created_at=timestamp(row[0]),
                facility=str(row[1]), department=str(row[2]), before=before, after=after,
                photo_id=drive_id(row[12]), policy='LEGACY-UNKNOWN', status='완료' if after else '접수',
                revision=1, legacy_values=row)


def migration_rows(rows, identity):
    if not rows: return []
    header = rows[0]
    if header[:13] != HEADERS[:13] or any(v and (i >= len(HEADERS) or v != HEADERS[i]) for i, v in enumerate(header)):
        raise ValueError('기존 헤더가 예상 형식과 다릅니다. 자동 이관을 중단합니다.')
    changes = []
    seen = set()
    for index, row in enumerate(rows[1:], 1):
        if not any(str(v).strip() for v in row): continue
        if any(str(v).strip() for v in row[23:]):
            raise ValueError(f'{index+1}행: 관리 범위 밖 데이터가 있습니다.')
        if len(row) > 22 and row[22]:
            record = json.loads(row[22])
            if record['id'] != row[18] or record['id'] in seen:
                raise ValueError(f'{index+1}행: ID가 중복되거나 일치하지 않습니다.')
            seen.add(record['id'])
            continue
        if any(str(v).strip() for v in row[18:]):
            raise ValueError(f'{index+1}행: S:W 열을 이미 사용하고 있습니다.')
        try:
            record = legacy_record(row, f'{identity}:{index}:{digest(row[:18])}')
        except (ValueError, TypeError, IndexError) as exc:
            raise ValueError(f'{index+1}행: {exc}') from exc
        changes.append((index, [record['id'], record['policy'], record['status'], record['revision'], json.dumps(record, ensure_ascii=False)]))
    return changes


def main():
    parser = argparse.ArgumentParser(description='기존 A:R 보존, S:W 확장 및 조치이력 생성. 기본은 미리보기.')
    parser.add_argument('--apply', action='store_true', help='백업 저장 후 변경을 적용합니다.')
    args = parser.parse_args()
    settings = Settings()
    settings.validate_runtime()
    if settings.demo: raise SystemExit('APP_ENV=development 설정과 별도 Google 저장소가 필요합니다.')
    svc = google_client(settings, 'sheets', 'v4').spreadsheets()
    meta = svc.get(spreadsheetId=settings.spreadsheet_id, fields='sheets.properties').execute()
    props = {s['properties']['title']: s['properties'] for s in meta['sheets']}
    names = (settings.sheet_name, settings.history_sheet_name)
    snapshots = {name: svc.values().get(spreadsheetId=settings.spreadsheet_id, range=quoted(name), valueRenderOption='FORMATTED_VALUE').execute().get('values', []) if name in props else [] for name in names}
    changes = migration_rows(snapshots[names[0]], settings.spreadsheet_id + ':' + names[0])
    history = snapshots[names[1]]
    if history and history[0] != HISTORY_HEADERS:
        raise SystemExit('조치이력이라는 이름의 다른 시트가 있습니다. HISTORY_SHEET_NAME을 변경하세요.')
    print(f'이관 대상 {len(changes)}행. 기존 A:R 값 보존. 실행 모드: {"적용" if args.apply else "미리보기 (쓰기 없음)"}')
    if not args.apply: return
    folder = ROOT / 'artifacts' / 'migration-backups'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.json')
    path.write_text(json.dumps({'at':now(), 'spreadsheet_id':settings.spreadsheet_id, 'properties':props, 'sheets':snapshots}, ensure_ascii=False, indent=2), encoding='utf-8')
    requests = []
    for name, header in [(names[0], HEADERS), (names[1], HISTORY_HEADERS)]:
        if name not in props:
            sheet_id = max([p['sheetId'] for p in props.values()] + [0]) + 1
            props[name] = {'sheetId': sheet_id, 'gridProperties': {'columnCount': max(26, len(header))}}
            requests.append({'addSheet': {'properties': {'sheetId': sheet_id, 'title':name}}})
        prop = props[name]
        if prop['gridProperties']['columnCount'] < len(header):
            requests.append({'appendDimension': {'sheetId':prop['sheetId'], 'dimension':'COLUMNS', 'length':len(header)-prop['gridProperties']['columnCount']}})
        requests.append({'updateCells': {'start': {'sheetId':prop['sheetId'], 'rowIndex':0, 'columnIndex':0}, 'rows':[cells(header)], 'fields':'userEnteredValue'}})
    for index, values in changes:
        requests.append({'updateCells': {'start': {'sheetId':props[names[0]]['sheetId'], 'rowIndex':index, 'columnIndex':18}, 'rows':[cells(values)], 'fields':'userEnteredValue'}})
    svc.batchUpdate(spreadsheetId=settings.spreadsheet_id, body={'requests':requests}).execute()
    print(f'이관 완료. 백업: {path}')


if __name__ == '__main__': main()
