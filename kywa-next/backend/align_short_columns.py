"""Back up and center existing short-answer columns without rewriting any evaluation."""
import json
from datetime import datetime
from pathlib import Path
from .repository import SheetsRepository
from .sheet_sync import GoogleRows,CONFIG
from .sheet_schema import SheetSchemaError
from .column_alignment import center_requests,centered_template


def align(settings,apply=False,backup_dir='local-data/alignment-backups'):
    repo=SheetsRepository(settings);g=GoogleRows(repo)
    before=g.snapshot()[:3];entries=g.entries()
    if CONFIG not in entries or entries[CONFIG][1].get('version')!=2:
        raise SheetSchemaError('행 식별 관리 정보를 먼저 준비하세요.')
    if before[2] or any(kind in ('request','edit') and value.get('state') in ('pending','appending')
            for (kind,_),(_,value) in entries.items()):
        raise SheetSchemaError('미완료 저장 요청을 먼저 복구한 뒤 정렬하세요.')
    requests=center_requests(g.layout,g.sheet_id)
    columns=[r['repeatCell']['range']['startColumnIndex'] for r in requests]
    result={'organization':settings.organization_id,'columns':[g.layout.header[i] for i in columns],
        'records':len(before[0])-1,'applied':False}
    if not apply:return result
    full=g.api.get(spreadsheetId=g.sid,includeGridData=True).execute()
    folder=Path(backup_dir)/settings.organization_id;folder.mkdir(parents=True,exist_ok=True)
    backup=folder/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
    backup.write_text(json.dumps(full,ensure_ascii=False),encoding='utf-8')
    if g.snapshot()[:3]!=before:
        raise SheetSchemaError('백업 중 평가가 변경되었습니다. 다시 확인하세요.')
    fresh=GoogleRows(repo).entries()
    if fresh.get(CONFIG)!=entries[CONFIG]:
        raise SheetSchemaError('백업 중 기준 서식이 변경되었습니다. 다시 확인하세요.')
    template={**entries[CONFIG][1],'formats':centered_template(entries[CONFIG][1]['formats']),
        'short_alignment_version':1}
    # One atomic batch: short-column horizontal alignment and the future-row template.
    g.save([(*CONFIG,template)],extra=requests)
    after=GoogleRows(repo).snapshot()
    if after[:3]!=before:
        raise SheetSchemaError('정렬 중 평가 값이나 행 연결 변경이 감지됐습니다. 백업을 확인하세요.')
    formats=after[3]
    canonical_columns=[i for i,p in enumerate(g.layout.positions) if p in columns]
    for row in range(1,len(after[0])):
        if any(formats.get(row,[])[i].get('horizontalAlignment')!='CENTER' for i in canonical_columns):
            raise SheetSchemaError('가운데 정렬 결과를 확인하지 못했습니다.')
    return {**result,'applied':True,'backup':str(backup),'values_and_ids_preserved':True}


if __name__=='__main__':
    import argparse
    from .config import Settings
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true');p.add_argument('--backup-dir',default='local-data/alignment-backups')
    a=p.parse_args();cfg=Settings();cfg.validate_runtime()
    print(json.dumps(align(cfg,a.apply,a.backup_dir),ensure_ascii=False))
