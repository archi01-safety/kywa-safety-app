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


def migration_rows(rows, identity, include_name=False):
    if not rows: return []
    header = rows[0]
    expected = HEADERS + (['제출자 성명'] if include_name else [])
    if header[:13] != HEADERS[:13] or any(v and (i >= len(expected) or v != expected[i]) for i, v in enumerate(header)):
        raise ValueError('기존 헤더가 예상 형식과 다릅니다. 자동 이관을 중단합니다.')
    if include_name and header[23:24] != ['제출자 성명'] and any(len(row) > 23 and str(row[23]).strip() for row in rows[1:]):
        raise ValueError('X열에 기존 데이터가 있어 성명 열을 추가할 수 없습니다.')
    changes = []
    seen = set()
    for index, row in enumerate(rows[1:], 1):
        if not any(str(v).strip() for v in row): continue
        if any(str(v).strip() for v in row[len(expected):]):
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


def preparation_plan(rows, history, org):
    from .sheet_schema import Layout, expanded_header
    header = expanded_header(rows, org)
    if history and history[0] != HISTORY_HEADERS:
        raise ValueError('조치이력이라는 이름의 다른 시트가 있습니다. HISTORY_SHEET_NAME을 변경하세요.')
    layout = Layout(header, org)
    seen, legacy = set(), 0
    for index, row in enumerate(rows[1:], 1):
        if not any(str(v).strip() for v in row): continue
        record = layout.decode(row, index, 'preflight')
        if record['id'] in seen: raise ValueError('중복된 평가 ID가 있습니다.')
        seen.add(record['id'])
        legacy += not bool(layout.value(row, 'data'))
    return header, legacy


def prepare_storage(settings, apply=False):
    # Callable independently of AI/OAuth settings: this command only accesses Google storage.
    settings.validate_google_identity()
    from .check_connections import verify_targets, header_edit_allowed
    verify_targets(settings)
    svc = google_client(settings, 'sheets', 'v4').spreadsheets()
    meta = svc.get(spreadsheetId=settings.spreadsheet_id,
        fields='sheets(properties,protectedRanges(range,warningOnly,requestingUserCanEdit))').execute()
    props = {s['properties']['title']:s['properties'] for s in meta['sheets']}
    names = (settings.sheet_name, settings.history_sheet_name)
    if names[0] not in props:
        raise ValueError('기존 평가 탭을 찾을 수 없습니다. 새 탭을 만들지 않고 중단합니다.')
    def read(name):
        return svc.values().get(spreadsheetId=settings.spreadsheet_id, range=quoted(name),
            valueRenderOption='FORMATTED_VALUE').execute().get('values', []) if name in props else []
    snapshots = {name:read(name) for name in names}
    header, legacy = preparation_plan(snapshots[names[0]], snapshots[names[1]], settings.organization)
    old_header = snapshots[names[0]][0] if snapshots[names[0]] else []
    offset = len(old_header)
    while offset and old_header[offset-1] == '': offset -= 1
    result = dict(organization=settings.organization_id, legacy_rows=legacy,
                  added_headers=header[offset:], history_needed=not bool(snapshots[names[1]]), applied=False)
    main_sheet=next(s for s in meta['sheets'] if s['properties']['title']==names[0])
    result['header_edit_allowed']=header_edit_allowed(main_sheet,offset,len(header))
    if not apply: return result
    if not result['header_edit_allowed']:
        raise ValueError('평가 탭의 헤더가 보호되어 있습니다. 소유자가 관리 헤더를 준비하거나 보호 범위 편집을 허용해야 합니다.')
    folder = ROOT/'local-data'/'migration-backups'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(settings.organization_id+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json')
    path.write_text(json.dumps({'at':now(),'spreadsheet_id':settings.spreadsheet_id,
        'properties':props,'sheets':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')
    # Allow old apps to append between reads, but reject changes to already inspected data.
    fresh = {name:read(name) for name in names}
    for name in names:
        if fresh[name][:len(snapshots[name])] != snapshots[name]:
            raise ValueError('미리보기 이후 기존 내용이 변경되어 중단했습니다. 다시 확인하세요.')
    checked, _ = preparation_plan(fresh[names[0]], fresh[names[1]], settings.organization)
    if checked != header: raise ValueError('미리보기 이후 열 구성이 변경되었습니다.')
    requests = []
    main_prop = props[names[0]]
    capacity = main_prop['gridProperties']['columnCount']
    if capacity < len(header):
        requests.append({'appendDimension':{'sheetId':main_prop['sheetId'], 'dimension':'COLUMNS', 'length':len(header)-capacity}})
    if header[offset:]:
        requests.append({'updateCells':{'start':{'sheetId':main_prop['sheetId'],'rowIndex':0,'columnIndex':offset},
            'rows':[cells(header[offset:])],'fields':'userEnteredValue'}})
    if names[1] not in props:
        new_id = max([p['sheetId'] for p in props.values()]+[0])+1
        requests.append({'addSheet':{'properties':{'sheetId':new_id,'title':names[1]}}})
        props[names[1]] = {'sheetId':new_id}
    if not fresh[names[1]]:
        requests.append({'updateCells':{'start':{'sheetId':props[names[1]]['sheetId'],'rowIndex':0,'columnIndex':0},
            'rows':[cells(HISTORY_HEADERS)],'fields':'userEnteredValue'}})
    if requests: svc.batchUpdate(spreadsheetId=settings.spreadsheet_id,body={'requests':requests}).execute()
    result.update(applied=True,backup=str(path))
    return result


def main():
    parser = argparse.ArgumentParser(description='기존 열 보존·관리 헤더 확장. 기본은 미리보기이며 기존 평가 행은 수정하지 않습니다.')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--organization',default=None)
    args=parser.parse_args()
    from .check_connections import target_settings
    cfg=target_settings(args.organization)
    try:
        print(json.dumps(prepare_storage(cfg,args.apply),ensure_ascii=False,indent=2))
    except (ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        raise SystemExit('Google 연결 또는 적용 결과를 확인하지 못했습니다. 재실행 전 헤더와 백업을 확인하세요.') from None


if __name__ == '__main__': main()
