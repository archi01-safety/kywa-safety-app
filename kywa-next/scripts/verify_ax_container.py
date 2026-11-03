"""CI only: non-root, read-only image, persistent private data, assigned port, restart."""
import io
import json
from pathlib import Path
import subprocess
import time
import uuid

import httpx
from PIL import Image

PREFIX='/apps/kywa-safety'
ORIGIN='http://127.0.0.1:18507'
name='safety-ax-'+uuid.uuid4().hex[:10]
volume=name+'-data'
image='kywa-safety:ax'


def docker(*args):
    return subprocess.check_output(['docker',*args],text=True).strip()


def ready():
    for _ in range(90):
        try:
            r=httpx.get(ORIGIN+PREFIX+'/healthz')
            if r.status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(1)
    raise RuntimeError('AX test server did not become ready')


def run():
    docker('volume','create',volume)
    try:
        # Prepare only this disposable test volume, never host/service configuration.
        docker('run','--rm','--user','0','-v',volume+':/runtime','--entrypoint','chown',image,'10001:10001','/runtime')
        docker('run','-d','--name',name,'--read-only','-p','127.0.0.1:18507:8507',
               '-v',volume+':/runtime','-e','APP_ENV=demo','-e','APP_BASE_URL='+ORIGIN,
               '-e','APP_BASE_PATH='+PREFIX,'-e','APP_DATA_DIR=/runtime','-e','PORT=8507',image)
        ready()
        assert docker('exec',name,'id','-u')=='10001'
        assert docker('exec',name,'python','-c','from pathlib import Path; assert not __import__("os").access("/app",__import__("os").W_OK); print("readonly")')=='readonly'
        with httpx.Client(base_url=ORIGIN,timeout=120) as c:
            home=c.get(PREFIX+'/');assert home.status_code==200 and PREFIX+'/_next/' in home.text
            boot=c.get(PREFIX+'/api/bootstrap').json()
            c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':boot['csrf']})
            raw=io.BytesIO();Image.new('RGB',(90,60),'gray').save(raw,'WEBP')
            r=c.post(PREFIX+'/api/photos/prepare',files={'photo':('wrong.jpg',raw.getvalue(),'image/jpeg')})
            assert r.status_code==200,r.text
            photo=c.post(PREFIX+'/api/photos/'+r.json()['id']+'/deidentify',json={}).json()
            draft=c.post(PREFIX+'/api/analyses',data={'facility':boot['facilities'][0],'department':boot['departments'][0],
                'description':'AX 합성 검증용 난간','photo_id':photo['id']}).json()
            item=draft['items'][0]
            payload={'submitter_name':'홍㉠㉢','request_id':str(uuid.uuid4()),'draft_id':draft['draft_id'],
                'items':[dict(index=0,location=item['location'],scenario=item['scenario'],solution=item['solution'])]}
            saved=c.post(PREFIX+'/api/assessments',json=payload);assert saved.status_code==200,saved.text
            assert c.post(PREFIX+'/api/assessments',json=payload).json()['replayed']
            assert c.post(PREFIX+'/api/auth/demo',data={'role':'admin'}).status_code==200
            for format in ('xlsx','pdf','hwpx'):
                start=c.post(PREFIX+'/api/report-jobs',json={'format':format})
                assert start.status_code==200,start.text
                path=PREFIX+'/api/report-jobs/'+start.json()['id']
                for _ in range(180):
                    state=c.get(path).json()
                    if state['state'] in ('complete','failed'):break
                    time.sleep(.25)
                assert state['state']=='complete',state
                output=c.get(path+'/download');assert output.status_code==200,output.text[:100]
                assert output.content.startswith(b'%PDF' if format=='pdf' else b'PK')
            before=c.get(PREFIX+'/api/overview').json()['total']
        docker('stop','--time','15',name)
        assert docker('inspect','-f','{{.State.ExitCode}}',name)=='0'
        docker('start',name);ready()
        assert httpx.get(ORIGIN+PREFIX+'/api/overview').json()['total']==before
        assert docker('exec',name,'python','-c','from pathlib import Path; assert list(Path("/runtime/photos").glob("*.jpg")); print("persisted")')=='persisted'
        result={'status':'PASS','read_only_source':True,'uid':10001,'port':8507,'base_path':PREFIX,
                'upload_submit_retry':True,'formats':['xlsx','pdf','hwpx'],'sigterm_exit':0,'restart_persistence':True,
                'live_external_apis':'NOT TESTED (synthetic demo)','rocky_apache_systemd':'NOT TESTED'}
        Path('artifacts').mkdir(exist_ok=True)
        Path('artifacts/ax-container-verification.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    finally:
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['docker','volume','rm',volume],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':run()
