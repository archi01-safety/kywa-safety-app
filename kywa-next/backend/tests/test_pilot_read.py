from copy import deepcopy
import json
import pytest
from backend.compact_storage import HEAD,TAB,VISIBLE
from backend.pilot_read import NeedsSync,unpack
from backend.sheet_sync import KEY,fingerprint


def grid(values):
    return {'values':[{'effectiveValue':{'numberValue' if isinstance(v,(int,float)) else 'stringValue':v}} for v in values]}


@pytest.fixture()
def fixture():
    r=[46000,'중앙','시험','계단','보행 안전','합성',2,2,4,'낮음','정비','확인']
    rec={'id':'a','status':'완료'}
    meta={'hash':fingerprint(r),'record':rec}
    return {'properties':{'title':'KYWA 합성 평가 150건'},'sheets':[
        {'properties':{'title':'평가'},'data':[{'rowData':[grid(VISIBLE),grid(r)],'rowMetadata':[{}, {'developerMetadata':[{'metadataKey':KEY,'metadataValue':'a'}]}]}]},
        {'properties':{'title':TAB},'data':[{'rowData':[grid(HEAD),grid(['record','a',json.dumps(meta)])]}]}]}


def test_unchanged(fixture):
    assert unpack(fixture,'평가')==[{'id':'a','status':'완료'}]


@pytest.mark.parametrize('change',['delete','edit','legacy','pending','duplicate','invalid'])
def test_reconcile_on_writer(fixture,change):
    visible=fixture['sheets'][0]['data'][0]; hidden=fixture['sheets'][1]['data'][0]
    if change=='delete':visible['rowData'].pop()
    if change=='edit':visible['rowData'][1]['values'][5]={'effectiveValue':{'stringValue':'수정'}}
    if change=='legacy':visible['rowMetadata'].pop()
    if change=='pending':hidden['rowData'].append(grid(['request','x','{"state":"appending"}']))
    if change=='duplicate':visible['rowData'].append(deepcopy(visible['rowData'][1]))
    if change=='invalid':visible['rowData'][1]['values'][6]={'effectiveValue':{'stringValue':'오류'}}
    with pytest.raises(NeedsSync):
        unpack(fixture,'평가')


def test_another_workbook_is_rejected(fixture):
    fixture['properties']['title']='다른 파일'
    with pytest.raises(ValueError):
        unpack(fixture,'평가')


def _handler(path, overview, monkeypatch):
    from backend import pilot_endpoint as endpoint
    from io import BytesIO
    handler=object.__new__(endpoint.PilotReadHandler)
    handler.path=path;handler.overview=overview;handler.headers={'Cookie':'test-session'}
    handler.wfile=BytesIO()
    response={}
    handler.send_response=lambda s:response.update(status=s)
    handler.send_header=lambda k,v:response.update({k:v})
    handler.end_headers=lambda:None
    return handler,response,endpoint


def test_private_list_denies_expired_session_before_read(monkeypatch):
    from unittest.mock import Mock
    h,r,ep=_handler('/api/assessments',False,monkeypatch)
    auth=Mock();auth.json.return_value={'active':False}
    monkeypatch.setattr(ep.requests,'get',lambda *a,**kw:auth)
    monkeypatch.setattr(ep,'read_records',lambda *a:pytest.fail('unauthorized read'))
    h.do_GET()
    assert r['status']==401 and r['Cache-Control']=='private, no-store' and r['Vercel-CDN-Cache-Control']=='no-store'


@pytest.mark.parametrize('query,cache',[('year=2026',True),('year=2026&fresh=1',False)])
def test_public_cdn_only_for_cached_summary(query,cache,monkeypatch):
    from backend.config import Settings
    from backend.overview import summarize
    h,r,ep=_handler('/api/overview?'+query,True,monkeypatch)
    cfg=Settings(_env_file=None)
    records=[{'created_at':'2026-05-02','facility':'평창','status':'완료','submitter_name':'비공개','before':{'category':'시설 안전'}}]
    monkeypatch.setattr(ep,'settings',lambda:cfg)
    monkeypatch.setattr(ep,'read_records',lambda _:records)
    h.do_GET()
    assert r['status']==200 and ('s-maxage=30' in r['Vercel-CDN-Cache-Control'])==cache
    assert json.loads(h.wfile.getvalue())==summarize(records,2026,cfg.organization)


def test_list_fallback_carries_cookie_issues_and_never_caches(monkeypatch):
    from unittest.mock import Mock
    h,r,ep=_handler('/api/assessments?facility=F',False,monkeypatch)
    auth=Mock();auth.json.return_value={'active':True}
    fallback=Mock(status_code=200);fallback.json.return_value={'items':[],'issues':[{'row':27}]}
    get=Mock(side_effect=[auth,fallback]);monkeypatch.setattr(ep.requests,'get',get)
    monkeypatch.setattr(ep,'settings',lambda:object())
    def dirty(_):raise NeedsSync()
    monkeypatch.setattr(ep,'read_records',dirty)
    h.do_GET()
    assert json.loads(h.wfile.getvalue())==fallback.json.return_value
    assert get.call_args.kwargs['headers']=={'Cookie':'test-session'}
    assert get.call_args.kwargs['params']=={'facility':'F'} and r['Cache-Control']=='private, no-store'
