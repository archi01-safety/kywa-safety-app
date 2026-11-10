"""Synthetic legacy append/edit/delete. Never run against an operational file."""
import argparse
import os
import sys
import time
import subprocess
from uuid import uuid4
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.repository import google_client,quoted
from backend.domain import now


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('origin',choices=['https://kywa-safety-pilot-api.onrender.com','https://kywa-safety-pilot.vercel.app'])
    parser.add_argument('--ui',action='store_true',help='Measure a real browser refreshing after a synthetic direct edit')
    args=parser.parse_args(); origin=args.origin
    c=Settings(_env_file=None); book=c.spreadsheet_id
    assert book and book!=c.organization.storage.spreadsheet_id
    drive=google_client(c,'drive','v3')
    info=drive.files().get(fileId=book,fields='name,appProperties',supportsAllDrives=True).execute()
    assert info['name']=='KYWA 합성 평가 150건' and info['appProperties']['kywa_fixture']=='vercel-pilot-v1'
    sh=google_client(c,'sheets','v4').spreadsheets()
    tab=quoted(c.sheet_name); meta=sh.get(spreadsheetId=book,fields='sheets(properties(sheetId,title))').execute()
    gid=next(t['properties']['sheetId'] for t in meta['sheets'] if t['properties']['title']==c.sheet_name)
    ss=requests.Session(); ss.headers['Origin']=origin
    def get(route,**q):
        r=ss.get(origin+'/api'+route,params=q,timeout=70,allow_redirects=False); assert r.status_code==200,(route,r.status_code)
        return r.json()
    ss.headers['X-CSRF-Token']=get('/bootstrap')['csrf']
    assert ss.post(origin+'/api/auth/pin',data={'pin':os.environ['PILOT_PIN']},timeout=30,allow_redirects=False).status_code==200
    mark='PILOT-QA-'+uuid4().hex
    day=now()[:10]; yr=int(day[:4])
    def summary():return get('/overview',year=yr,fresh=1,t=uuid4().hex)['total']
    def load():return get('/assessments',start=day,end=day)
    def find():
        vs=sh.values().get(spreadsheetId=book,range=tab+'!D:D').execute().get('values',[])
        matches=[i+1 for i,v in enumerate(vs) if v==[mark]]
        if len(matches)!=1: raise ValueError('Test row not uniquely identified')
        return matches[0]
    def set_cell(col,value):
        r=find()
        sh.values().update(spreadsheetId=book,range=f'{tab}!{col}{r}',valueInputOption='RAW',body={'values':[[value]]}).execute()
    original=summary()
    legacy=[now(),c.organization.facilities[0],c.organization.departments[0],mark,c.organization.categories[0],'합성 시트 수정 시험',1,1,1,'매우 낮음','단차 정비','시험 자료','사진 없음']
    if args.ui:
        script=Path(__file__).resolve().parents[1]/'frontend/scripts/bench-visible-edit.mjs'
        proc=subprocess.Popen([os.environ.get('PILOT_NODE','node'),str(script),origin,mark],
                              stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8')
        def visible(phase):
            proc.stdin.write(phase+'\n');proc.stdin.flush()
            result=proc.stdout.readline().strip()
            if not result:raise RuntimeError('Browser refresh did not finish: '+phase)
            print(origin,result,flush=True)
        try:
            if proc.stdout.readline().strip()!='READY':raise RuntimeError('Browser not ready')
            sh.values().append(spreadsheetId=book,range=tab+'!A:S',valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':[legacy]}).execute()
            try:
                visible('add');set_cell('F','수정된 합성 위험상황');visible('edit')
            finally:
                r=find()
                sh.batchUpdate(spreadsheetId=book,body={'requests':[{'deleteDimension':{'range':{'sheetId':gid,'dimension':'ROWS','startIndex':r-1,'endIndex':r}}}]}).execute()
            visible('delete')
            proc.stdin.close()
            if proc.wait(timeout=15)!=0 or summary()!=original:raise RuntimeError('Fixture not restored')
        finally:
            if proc.poll() is None:proc.kill();proc.wait(timeout=10)
        return
    sh.values().append(spreadsheetId=book,range=tab+'!A:S',valueInputOption='RAW',insertDataOption='INSERT_ROWS',body={'values':[legacy]}).execute()
    start=time.perf_counter()
    try:
        assert summary()==original+1
        rows=load()['items']; rec=next(r for r in rows if r['before']['location']==mark)
        print('legacy append -> updated charts/list ms',round((time.perf_counter()-start)*1000),flush=True)
        set_cell('F','수정된 합성 위험상황');start=time.perf_counter()
        assert next(r for r in load()['items'] if r['id']==rec['id'])['before']['scenario']=='수정된 합성 위험상황'
        print('sheet edit -> refreshed list ms',round((time.perf_counter()-start)*1000),flush=True)
        set_cell('G','잘못된 숫자')
        assert load()['issues']
        print('PASS: invalid synthetic row isolated',flush=True)
    finally:
        r=find()
        sh.batchUpdate(spreadsheetId=book,body={'requests':[{'deleteDimension':{'range':{'sheetId':gid,'dimension':'ROWS','startIndex':r-1,'endIndex':r}}}]}).execute()
    assert summary()==original and all(r['before']['location']!=mark for r in load()['items'])
    print('PASS: deletion reflected and original count restored',flush=True)


if __name__=='__main__':main()
