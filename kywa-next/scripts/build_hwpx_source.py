"""Keep the editable report adapter, vendor source and licenses with its bundled runtime."""
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parent.parent
source=root/'tools/hwpx'
if not (source/'entry.ts').is_file():
    raise SystemExit('backend/assets/hwpx-semantic-source.zip을 tools/hwpx에 풀고 수정·빌드한 뒤 실행하세요.')
files=[source/name for name in ('entry.ts','build.mjs','package.json','package-lock.json')]
files+=list((source/'vendor').rglob('*.ts'))+list((source/'licenses').rglob('*'))
files+=[p for p in (source/'vendor').rglob('*') if p.name.lower().startswith(('license','notice'))]
with zipfile.ZipFile(root/'backend/assets/hwpx-semantic-source.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        if path.is_file():archive.write(path,path.relative_to(source))
with zipfile.ZipFile(root/'backend/assets/hwpx-semantic-source.zip') as archive:
    assert archive.testzip() is None
    assert not any('node_modules/' in name for name in archive.namelist())
print('HWPX source archive verified')
