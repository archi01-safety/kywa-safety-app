"""Package only the public static files, not the app, samples, or private diagnostics."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--commit');a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.commit:
        if not re.fullmatch('[0-9a-f]{40}',a.commit):raise ValueError('Use an exact source commit SHA')
        prefix='kywa-next/entry-screen/site/'
        names=subprocess.check_output(['git','ls-tree','-r','--name-only',a.commit,'--',prefix],cwd=ROOT.parent.parent,text=True).splitlines()
        files=[(name[len(prefix):],subprocess.check_output(['git','show',a.commit+':'+name],cwd=ROOT.parent.parent)) for name in names]
    else:files=[(f.relative_to(ROOT/'site').as_posix(),f.read_bytes()) for f in sorted((ROOT/'site').rglob('*')) if f.is_file()]
    if not files or not any(name=='index.html' for name,_ in files):raise ValueError('Static entry page is missing')
    entries=[]
    with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files:
            if Path(name).suffix.lower() in ('.env','.pem','.pdf','.mp4','.zip'):raise ValueError('Unexpected public file')
            info=zipfile.ZipInfo(name,date_time=(2026,11,18,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data);entries.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'artifact':a.output.name,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),
        'bytes':a.output.stat().st_size,'sourceCommit':a.commit,'files':entries,'credentials_included':False}
    a.output.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('artifact','bytes','sha256')},ensure_ascii=False))
if __name__=='__main__':main()
