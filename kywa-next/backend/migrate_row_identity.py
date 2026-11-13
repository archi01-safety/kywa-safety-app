"""Prepare KYWA row identities after copy validation and pausing app writes.

python -m backend.migrate_row_identity [--apply] [--backup-dir local-data/row-backups]
Requires configured server environment; never put secrets on the command line.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from .config import Settings
from .repository import SheetsRepository, google_client
from .sheet_sync import prepare


def migrate(settings, apply=False, backup_dir='local-data/row-backups'):
    if settings.organization.id!='kywa': raise ValueError('KYWA에만 적용할 수 있습니다.')
    repo=SheetsRepository(settings)
    plan=prepare(repo)
    if not apply or plan.get('already_prepared'): return plan
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    directory=Path(backup_dir);directory.mkdir(parents=True,exist_ok=True)
    sheets=google_client(settings,'sheets','v4').spreadsheets()
    full=sheets.get(spreadsheetId=settings.spreadsheet_id,includeGridData=True).execute()
    path=directory/f'row-identity-{stamp}.json'
    path.write_text(json.dumps(full,ensure_ascii=False),encoding='utf-8')
    drive=google_client(settings,'drive','v3')
    parents=drive.files().get(fileId=settings.spreadsheet_id,fields='parents',supportsAllDrives=True).execute()['parents']
    backup=drive.files().copy(fileId=settings.spreadsheet_id,body={'name':f'KYWA 행 연결 개선 전 백업 {stamp}','parents':parents},
        supportsAllDrives=True,fields='id').execute()
    path.with_suffix('.cloud.json').write_text(json.dumps(backup),encoding='utf-8')
    result=prepare(repo,apply=True)
    return {**result,'local_backup':str(path),'cloud_backup_created':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup-dir',default='local-data/row-backups')
    args=parser.parse_args()
    settings=Settings();settings.validate_runtime()
    print(json.dumps(migrate(settings,args.apply,args.backup_dir),ensure_ascii=False))
