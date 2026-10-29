"""Single-writer repositories. Google updates and audit rows share one atomic batch.

Use ONE uvicorn worker/Render instance. Append-only Streamlit submissions may run concurrently. Direct row moves, deletes
or manual edits during writes are unsupported; a spreadsheet is not a transactional multi-writer DB.
"""
import copy
import io
import json
import os
import threading
from pathlib import Path

from .domain import HEADERS, HISTORY_HEADERS, now, risk, sheet_row, POLICY
from .sheet_schema import Layout, SheetSchemaError, MANAGED


class RepositoryError(Exception):
    pass


class DemoRepository:
    def __init__(self, path, org=None):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            examples = [('중앙', '본관 2층 테라스', '시설 안전', '난간 고정부 흔들림으로 추락 위험', '고정부 보강 후 흔들림 점검', 3, 4),
                        ('평창', '생활관 계단', '보행 안전', '계단 논슬립 마모로 미끄러질 위험', '논슬립 교체 및 통행 안내', 3, 2),
                        ('우주', '기계실 출입구', '전기적 요인', '전선 피복 손상으로 감전 위험', '전원 차단 후 손상 전선 교체', 4, 4),
                        ('본원', '사무실 복도', '보행 안전', '이동 통로 적치물로 넘어짐 위험', '적치물 제거 및 통로 표시', 2, 2)]
            records = []
            for i, (fac, loc, cat, scene, solution, p, s) in enumerate(examples):
                before = dict(category=cat, location=loc, scenario=scene, solution=solution,
                              law='샘플 데이터 · 현장 근거 확인 필요', **risk(p, s))
                after = dict(**risk(1, 2), text='샘플 조치내용: 적치물 정리 및 통로 확보', photo_id='',
                             actor='demo-admin@kywa.local', created_at=now(), policy=POLICY) if i == 3 else None
                records.append(dict(id=f'demo-{i+1}', created_at=now(), facility=fac,
                                    department='협력부(국립청소년시설)', before=before, after=after,
                                    photo_id='', policy=POLICY, status='완료' if after else '접수', revision=1))
            if org and org.id != 'kywa':
                records = []
            self._write({'records': records, 'events': []})

    def _read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def _write(self, data):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.path)

    def records(self):
        with self.lock:
            return copy.deepcopy(self._read()['records'])

    def events(self, record_id=None):
        with self.lock:
            return [e for e in self._read()['events'] if record_id is None or e['record_id'] == record_id]

    def apply(self, records, events):
        with self.lock:
            data = self._read()
            by_id = {r['id']: r for r in data['records']}
            by_id.update({r['id']: r for r in records})
            data['records'] = list(by_id.values())
            data['events'].extend(events)
            self._write(data)


def google_credentials(settings):
    from google.oauth2 import service_account
    info = json.loads(settings.google_service_account_json)
    info['private_key'] = info['private_key'].replace('\\n', '\n')
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    return credentials.with_subject(settings.google_delegate_email) if settings.google_delegate_email else credentials


def google_client(settings, service, version):
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2
    # Honor an explicitly configured, trusted CA bundle (e.g. managed Windows TLS inspection).
    # Certificate verification remains enabled.
    return build(service, version, http=AuthorizedHttp(google_credentials(settings),
        http=httplib2.Http(timeout=25, ca_certs=os.environ.get('SSL_CERT_FILE') or None)), cache_discovery=False)


def quoted(name):
    return "'" + name.replace("'", "''") + "'"


def cells(values):
    # stringValue prevents formula execution for user/AI text starting with =, +, - or @.
    return {'values': [{'userEnteredValue': {'numberValue': v} if type(v) in (int, float)
                        else {'stringValue': str(v)}} for v in values]}


class SheetsRepository:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.RLock()

    def _values(self, name):
        return google_client(self.settings, 'sheets', 'v4').spreadsheets().values().get(
            spreadsheetId=self.settings.spreadsheet_id, range=quoted(name)).execute().get('values', [])

    def _rows(self):
        rows = self._values(self.settings.sheet_name)
        if not rows:
            raise RepositoryError('기관 평가 탭이 비어 있습니다. migrate로 준비하세요.')
        Layout(rows[0], self.settings.organization)
        return rows

    def _decoded(self, rows):
        layout = Layout(rows[0], self.settings.organization)
        identity = self.settings.spreadsheet_id + ':' + self.settings.sheet_name
        records = [layout.decode(row, index, identity) for index,row in enumerate(rows[1:],1)
                   if any(str(v).strip() for v in row)]
        if len({r['id'] for r in records}) != len(records):
            raise RepositoryError('중복된 평가 ID가 있습니다. 원본을 확인하세요.')
        return records

    def records(self):
        return self._decoded(self._rows())

    def events(self, record_id=None):
        rows = self._values(self.settings.history_sheet_name)
        if not rows or rows[0][:7] != HISTORY_HEADERS:
            raise RepositoryError('조치이력 시트 초기화가 필요합니다.')
        events = [json.loads(row[6]) for row in rows[1:] if len(row) >= 7 and row[6]]
        return [e for e in events if record_id is None or e['record_id'] == record_id]

    def apply(self, records, events):
        with self.lock:
            svc = google_client(self.settings, 'sheets', 'v4').spreadsheets()
            meta = svc.get(spreadsheetId=self.settings.spreadsheet_id, fields='sheets.properties').execute()
            ids = {s['properties']['title']: s['properties']['sheetId'] for s in meta['sheets']}
            if self.settings.sheet_name not in ids or (events and self.settings.history_sheet_name not in ids):
                raise RepositoryError('평가·조치이력 탭 준비가 필요합니다.')
            rows = self._rows()
            layout = Layout(rows[0], self.settings.organization)
            layout.require_writable()
            current = {r['id']:r for r in self._decoded(rows)}
            requests, new_rows = [], []
            for record in records:
                previous = current.get(record['id'])
                if '_sheet_row' in record:
                    if (not previous or previous['_sheet_row'] != record['_sheet_row'] or
                        previous['_sheet_hash'] != record.get('_sheet_hash') or
                        previous['revision'] != record.get('_sheet_revision')):
                        raise RepositoryError('원본 행이 변경되었습니다. 목록을 새로고침한 뒤 다시 시도하세요.')
                    encoded = layout.encoded(record)
                    # Update only management cells. Original timestamps, names, formulas and links stay intact.
                    for key in MANAGED:
                        requests.append({'updateCells': {'start': {'sheetId': ids[self.settings.sheet_name],
                            'rowIndex':previous['_sheet_row'], 'columnIndex':layout.columns[key]},
                            'rows':[cells([encoded[key]])], 'fields':'userEnteredValue'}})
                elif previous:
                    raise RepositoryError('이미 존재하는 평가 ID입니다. 저장 결과를 먼저 확인하세요.')
                else:
                    new_rows.append(cells(layout.new_row(record)))
            if new_rows:
                requests.append({'appendCells': {'sheetId':ids[self.settings.sheet_name],
                                                'rows':new_rows, 'fields':'userEnteredValue'}})
            if events:
                history = self._values(self.settings.history_sheet_name)
                if not history or history[0][:7] != HISTORY_HEADERS:
                    raise RepositoryError('조치이력 시트 헤더를 확인하세요.')
                event_rows = [cells([e['id'],e['record_id'],e['at'],e['actor'],e['kind'],
                                    e.get('text',''),json.dumps(e,ensure_ascii=False)]) for e in events]
                requests.append({'appendCells': {'sheetId':ids[self.settings.history_sheet_name],
                                                'rows':event_rows, 'fields':'userEnteredValue'}})
            if requests:
                svc.batchUpdate(spreadsheetId=self.settings.spreadsheet_id, body={'requests':requests}).execute()


class DriveStore:
    def __init__(self, settings):
        self.settings = settings
        self.demo_dir = Path(settings.demo_data_path).parent / 'photos'

    def put(self, data: bytes, key: str):
        if not data:
            return ''
        if self.settings.demo:
            self.demo_dir.mkdir(parents=True, exist_ok=True)
            path = self.demo_dir / (key + '.jpg')
            path.write_bytes(data)
            return key
        from googleapiclient.http import MediaIoBaseUpload
        svc = google_client(self.settings, 'drive', 'v3')
        folder = self.settings.drive_folder_id
        organization = self.settings.organization_id
        q = f"'{folder}' in parents and trashed=false and appProperties has {{ key='kywaOperation' and value='{key}' }} and appProperties has {{ key='safetyOrganization' and value='{organization}' }}"
        found = svc.files().list(q=q, fields='files(id)', supportsAllDrives=True,
                                 includeItemsFromAllDrives=True).execute().get('files', [])
        if found:
            return found[0]['id']
        result = svc.files().create(body={'name': organization + '_' + key + '.jpg', 'parents': [folder],
                                         'appProperties': {'kywaOperation': key, 'safetyOrganization': organization}},
                                    media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype='image/jpeg', resumable=False),
                                    fields='id', supportsAllDrives=True).execute()
        # No anyone/reader permission: storage remains private.
        return result['id']

    def get(self, file_id):
        if not file_id:
            return None
        if self.settings.demo:
            path = self.demo_dir / (file_id + '.jpg')
            return path.read_bytes() if path.exists() else None
        return google_client(self.settings, 'drive', 'v3').files().get_media(
            fileId=file_id, supportsAllDrives=True).execute()
