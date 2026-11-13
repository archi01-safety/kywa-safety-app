"""Institution-scoped, source-addressed release manifests. No secrets or assessment data."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
ORGS=('kywa','ayf','fowi','knps','knf','kohi','khidi','cayf')
BASELINE='b180b29a5f9cdd39b30aa7d51e06c67584fb29cf'


def git(*args,check=True):
    return subprocess.run(['git','-C',str(ROOT),'-c','user.name=Codex','-c','user.email=codex@local.invalid',*args],capture_output=True,check=check).stdout


def manifest(org,version,commit,state):
    if org not in ORGS or not re.fullmatch(r'v\d+\.\d+\.\d+',version):raise ValueError('기관과 버전을 확인하세요.')
    source=git('rev-parse',commit+'^{commit}').decode().strip()
    raw=git('show',source+f':kywa-next/backend/organizations/{org}.json')
    config=json.loads(raw)
    prompts=git('show',source+':kywa-next/backend/prompts.py')
    profile=git('show',source+':kywa-next/backend/prompt_profiles/'+('cayf' if org=='ayf' else org)+'.txt',check=False)
    return {'format':1,'organization':org,'version':version,'tag':f'{org}/{version}','source_commit':source,
        'state':state,'site':f'https://{org}-safety.onrender.com',
        'organization_config_sha256':hashlib.sha256(raw).hexdigest(),
        'policy_version':config['policy']['version'],'prompt_version':config['prompt_version'],
        'prompt_source_sha256':hashlib.sha256(prompts+profile).hexdigest(),
        'sheet_schema':('ayf-visible17-row-metadata-v2' if org=='ayf' else 'visible19-row-metadata-v2') if version=='v1.0.0' else ('ayf-visible18-photo2-v1' if org=='ayf' else 'visible20-photo2-v1'),
        'data_rollback':'preserve_newer_records; archive additional photos/plans before a schema downgrade',
        'deployment':None,'verification':{'runtime_baseline_evidence':'HANDOFF.md 2026-11-10' if version=='v1.0.0' else None}}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','candidate','verify'])
    p.add_argument('--organization',choices=ORGS);p.add_argument('--version',default='v1.1.0');p.add_argument('--commit',default='HEAD');p.add_argument('--tag',action='store_true');a=p.parse_args()
    if a.action=='baseline':orgs=ORGS;version='v1.0.0';commit=BASELINE
    else:
        if not a.organization:p.error('--organization가 필요합니다.')
        orgs=(a.organization,);version=a.version;commit=a.commit
    out=[]
    for org in orgs:
        path=ROOT/'releases'/org/(version+'.json')
        if a.action=='verify':
            data=json.loads(path.read_text(encoding='utf-8'));actual=git('rev-parse',data['tag']+'^{commit}').decode().strip()
            assert actual==data['source_commit'],'버전 태그와 소스 커밋이 다릅니다.'
        else:
            data=manifest(org,version,commit,'baseline_registered' if a.action=='baseline' else 'candidate')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and json.loads(path.read_text(encoding='utf-8'))['source_commit']!=data['source_commit']:
                raise ValueError('이미 등록한 버전은 다른 커밋으로 덮어쓰지 않습니다. 패치 버전을 올리세요.')
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if a.tag:
                existing=git('rev-parse','--verify',data['tag']+'^{commit}',check=False).decode().strip()
                if existing and existing!=data['source_commit']:raise ValueError('다른 커밋을 가리키는 태그입니다.')
                if not existing:git('tag','-a',data['tag'],data['source_commit'],'-m',f'{org} {version}: source and institution configuration baseline')
        out.append({'organization':org,'version':version,'commit':data['source_commit']})
    print(json.dumps(out))


if __name__=='__main__':main()
