"""Exercise only the isolated pilot, with a synthetic photo and a single test submission."""
import argparse
import io
import json
import os
import time
import uuid
import zipfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ORIGINS = ['https://kywa-safety-pilot.vercel.app', 'https://kywa-safety-pilot-api.onrender.com']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('origin', choices=ORIGINS)
    p.add_argument('--reports-only', action='store_true')
    p.add_argument('--receipt',type=Path,help='Local receipt for the synthetic row; never use on business records.')
    args = p.parse_args()
    origin = args.origin
    s = requests.Session()
    s.headers.update({'Origin': origin})

    def call(method, path, **kw):
        r = s.request(method, origin + '/api' + path, timeout=150, allow_redirects=False, **kw)
        if not r.ok or r.is_redirect:
            raise RuntimeError(f'{method} {path.split("?")[0]}: HTTP {r.status_code}')
        return r

    def boot():
        b = call('GET', '/bootstrap').json()
        assert b['organization']['id'] == 'kywa' and b['auth_mode'] == 'pin'
        s.headers['X-CSRF-Token'] = b['csrf']
        return b

    b = boot()
    call('POST', '/auth/pin', data={'pin': os.environ['PILOT_PIN']})
    b = boot()
    assert b['user']['role'] == 'admin' and call('GET', '/auth/session').json()['active']
    listing = call('GET', '/assessments').json()['items']
    assert len(listing) >= 150 and sum(x['before']['scenario']=='합성 자료: 바닥 단차' for x in listing) >= 149
    filters = {'facility':listing[-1]['facility'], 'start':listing[-1]['created_at'][:10], 'end':listing[-1]['created_at'][:10]}
    if not args.reports_only:
        im = Image.new('RGB', (960,640), '#c5c7c9')
        d = ImageDraw.Draw(im)
        d.rectangle((0,350,959,639), fill='#9daeb1')
        d.line([(0,430),(180,408),(320,458),(510,388),(640,425),(959,390)], fill='#353638', width=12)
        f=io.BytesIO(); im.save(f,'JPEG')
        photo = call('POST','/photos/prepare', files={'photo':('synthetic.jpg',f.getvalue(),'image/jpeg')}).json()
        protected = call('POST','/photos/'+photo['id']+'/deidentify',json={}).json()
        assert protected['processed'] is True
        processed = call('GET',protected['url'].removeprefix('/api')).content
        a = call('POST','/analyses', data={'facility':b['facilities'][0],'department':b['departments'][0],
            'photo_id':protected['id'], 'description':'합성 시험용. 보행로 바닥에 균열이 있어 걸려 넘어질 수 있음.'}).json()
        item = dict(index=0, **{k:a['items'][0][k] for k in ('location','scenario','solution')})
        data={'request_id':str(uuid.uuid4()),'draft_id':a['draft_id'],'items':[item],'submitter_name':'시㉭'}
        res = call('POST','/assessments',json=data).json()
        rid=res['ids'][0]
        if args.receipt:
            args.receipt.write_text(json.dumps({'id':rid,'request_id':data['request_id'],'origin':origin}),encoding='utf-8')
        assert call('POST','/assessments',json=data).json()['replayed'] is True
        rows=call('GET','/assessments',params={'facility':b['facilities'][0]}).json()['items']
        row=next(r for r in rows if r['id']==rid)
        assert row['submitter_name']=='시㉭' and call('GET',row['photo_url'].removeprefix('/api')).content==processed
        print('PASS: photo -> face processing -> analysis -> submission/retry -> same Drive bytes',flush=True)
        after=call('POST','/assessments/'+rid+'/reassess',data={'text':'균열을 메우고 평탄화했습니다.'}).json()
        action=dict(request_id=str(uuid.uuid4()),draft_id=after['draft_id'],revision=row['revision'],p=after['p'],s=after['s'],complete=True)
        assert call('POST','/assessments/'+rid+'/actions',json=action).json()['item']['status']=='완료'
        filters={'facility':row['facility'],'start':row['created_at'][:10],'end':row['created_at'][:10]}
        print('PASS: corrective action and reassessment', flush=True)
    for fmt in ('xlsx','pdf','hwpx'):
        key=call('POST','/report-jobs',json={'format':fmt,**filters}).json()['id']
        deadline=time.monotonic()+220
        while time.monotonic()<deadline:
            job=call('GET','/report-jobs/'+key).json()
            if job['state']=='complete': break
            if job['state'] in ('failed','expired'): raise RuntimeError(f'{fmt}: '+str(job.get('error_code')))
            time.sleep(2)
        else: raise RuntimeError(fmt+' time limit')
        r=call('GET','/report-jobs/'+key+'/download')
        if fmt=='pdf': assert r.content.startswith(b'%PDF') and b'%%EOF' in r.content[-1024:]
        else:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                assert z.testzip() is None
                assert ('Contents/section0.xml' if fmt=='hwpx' else 'xl/workbook.xml') in z.namelist()
        assert ('filename*=' in r.headers['Content-Disposition'] and r.headers['Content-Disposition'].endswith('.'+fmt))
        print(f'PASS: {fmt} download ({len(r.content)} bytes)',flush=True)
    call('POST','/auth/logout',json={})
    assert s.get(origin+'/api/assessments',allow_redirects=False,timeout=30).status_code==401
    print('PASS: logout revokes list access',flush=True)


if __name__ == '__main__':
    main()
