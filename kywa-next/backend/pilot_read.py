"""Read the synthetic pilot workbook in one request, without invoking the writer."""
import json
import os
import threading
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from .compact_storage import HEAD, TAB, VISIBLE
from .repository import quoted
from .sheet_sync import KEY, NOTE, blank, fingerprint


class NeedsSync(Exception):
    """Only the Render writer may adopt, repair or reconcile a row."""


_local = threading.local()


def read_records(cfg):
    if not cfg.spreadsheet_id or cfg.organization_id != 'kywa' or cfg.spreadsheet_id == cfg.organization.storage.spreadsheet_id:
        raise ValueError('시험 시트 설정이 필요합니다.')
    if getattr(_local, 'cfg', None) is not cfg:
        credentials = Credentials.from_service_account_info(
            json.loads(cfg.google_service_account_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        _local.client = AuthorizedSession(credentials)
        _local.cfg = cfg
    response = _local.client.get(
        'https://sheets.googleapis.com/v4/spreadsheets/' + quote(cfg.spreadsheet_id, safe=''),
        params=[('ranges', quoted(cfg.sheet_name)+'!A:S'), ('ranges', quoted(TAB)+'!A:C'),
                ('fields','properties(title),sheets(properties(title),data(rowMetadata(developerMetadata(metadataKey,metadataValue)),rowData(values(effectiveValue,note))))')],
        verify=os.environ.get('SSL_CERT_FILE') or True, timeout=25)
    response.raise_for_status()
    return unpack(response.json(), cfg.sheet_name)


def unpack(doc, title):
    if doc['properties']['title'] != 'KYWA 합성 평가 150건':
        raise ValueError('지정한 파일이 KYWA 합성 시험 시트가 아닙니다.')
    sheets = {s['properties']['title']: s['data'][0] for s in doc['sheets']}
    def values(row):
        return [next(iter(cell.get('effectiveValue', {}).values()), '') for cell in row.get('values', [])]
    hidden = sheets[TAB]['rowData']
    grid = sheets[title]
    if values(hidden[0]) != HEAD or values(grid['rowData'][0]) != VISIBLE:
        raise NeedsSync()
    managed = {}
    for row in hidden[1:]:
        fields = values(row)
        if not fields or not any(fields):
            continue
        if len(fields) < 3:
            raise NeedsSync()
        kind, key, raw = fields[:3]
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            raise NeedsSync() from None  # chunked metadata is handled by the writer
        if kind == 'record' and not data.get('deleted'):
            if key in managed or data.get('issue'):
                raise NeedsSync()
            managed[key] = data
        if kind in ('request', 'edit') and data.get('state') in ('pending','appending'):
            raise NeedsSync()
    row_ids = grid.get('rowMetadata', [])
    records = []
    for i,row in enumerate(grid['rowData'][1:],1):
        cells = values(row)
        if blank(cells):
            continue
        if any(c.get('note','').startswith(NOTE) for c in row.get('values', [])):
            raise NeedsSync()
        ids = [m.get('metadataValue') for m in (row_ids[i] if i<len(row_ids) else {}).get('developerMetadata',[])
               if m.get('metadataKey') == KEY]
        if len(ids)!=1 or ids[0] not in managed:
            raise NeedsSync()
        entry = managed.pop(ids[0])
        if fingerprint(cells) != entry.get('hash'):
            raise NeedsSync()
        records.append(entry['record'])
    if managed:
        raise NeedsSync()
    return records
