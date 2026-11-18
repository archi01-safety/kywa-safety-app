"""Package only the public static files, not the app, samples, or private diagnostics."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    files=sorted(f for f in (ROOT/'site').rglob('*') if f.is_file());a.output.parent.mkdir(parents=True,exist_ok=True)
    entries=[]
    with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:
            name=f.relative_to(ROOT/'site').as_posix();data=f.read_bytes()
            if f.suffix.lower() in ('.env','.pem','.pdf','.mp4','.zip'):raise ValueError('Unexpected public file')
            info=zipfile.ZipInfo(name,date_time=(2026,11,18,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data);entries.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'artifact':a.output.name,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),
        'bytes':a.output.stat().st_size,'files':entries,'credentials_included':False}
    a.output.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('artifact','bytes','sha256')},ensure_ascii=False))
if __name__=='__main__':main()
