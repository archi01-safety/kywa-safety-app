"""Package a source-only allowlist. Never include local credentials, data, or runtimes."""
import hashlib
import json
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parent.parent
out=root/'artifacts'
out.mkdir(exist_ok=True)
patterns=['.gitignore','.dockerignore','.env.example','*.md','Dockerfile','render.yaml','pytest.ini',
          'backend/*.py','backend/requirements*','backend/tests/*.py','frontend/app/*.tsx','frontend/app/*.css',
          'frontend/public/*.png','frontend/package*.json','frontend/next.config.ts','frontend/next-env.d.ts',
          'frontend/tsconfig.json','frontend/playwright.config.ts','frontend/tests/*.ts','scripts/*.py','scripts/*.ps1','deploy/*.yml']
files=sorted({path for pattern in patterns for path in root.glob(pattern) if path.is_file()})
target=out/'kywa-safety-source.zip'
manifest=[]
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        name='kywa-next/'+path.relative_to(root).as_posix()
        data=path.read_bytes()
        archive.writestr(name,data)
        manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    for source,dest in [('ci.yml','kywa-next-ci.yml'),('health-check.yml','kywa-render-health.yml')]:
        data=(root/'deploy'/source).read_bytes()
        name='.github/workflows/'+dest
        archive.writestr(name,data)
        manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert all('/.env' not in name or name.endswith('/.env.example') for name in archive.namelist())
print(json.dumps({'file':str(target),'files':len(manifest),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
