import json
import re
import socket
from fastapi.testclient import TestClient
from backend.tests.test_system import context,login
from backend.main import create_app
from backend.law_links import LawLinks,citations,safe_url


def test_read_response_cannot_replace_later_login_cookie(context):
    c,app,repo,cfg=context
    old=c.cookies.get('kywa_session')
    login(c);authenticated=c.cookies.get('kywa_session');assert authenticated!=old
    # Simulate a request started before login whose response arrives afterwards.
    late=c.get('/api/overview',headers={'Cookie':'kywa_session='+old})
    assert late.status_code==200 and 'set-cookie' not in late.headers
    assert c.cookies.get('kywa_session')==authenticated
    assert c.get('/api/assessments').status_code==200
    assert 'set-cookie' not in c.get('/api/auth/session').headers


def test_timeout_has_safe_code_and_trace_number(context,monkeypatch):
    c,app,repo,cfg=context;login(c)
    def unavailable():raise TimeoutError('private record and test-secret must never be returned')
    monkeypatch.setattr(repo,'records',unavailable)
    with TestClient(app,raise_server_exceptions=False) as other:
        other.cookies.update(c.cookies)
        result=other.get('/api/assessments')
    assert result.status_code==504,result.text
    body=result.json();assert body['code']=='upstream_timeout' and body['retryable']
    assert re.fullmatch('[a-f0-9]{16}',body['request_id'])
    assert body['request_id']==result.headers['x-request-id']
    assert 'private record' not in result.text and 'test-secret' not in result.text


def test_law_fallback_multiple_citations_and_no_untrusted_urls():
    text='산업안전보건기준에 관한 규칙 제3조(전도의 방지), 제4조(작업장의 청결); 산업안전보건법 제38조'
    refs=LawLinks().resolve(text)
    assert len(refs)==3 and all(not x['verified'] and safe_url(x['url']) for x in refs)
    assert not safe_url('https://www.law.go.kr.evil.example/')
    assert not safe_url('javascript:alert(1)')
    assert not safe_url('https://www.law.go.kr/DRF/lawService.do?OC=private')
    assert not safe_url('https://evil@www.law.go.kr/')
    assert all('key' not in x for x in refs)


def test_law_api_verifies_title_article_and_effective_date_without_key_leak():
    import httpx
    seen=[]
    def get(url,**kwargs):
        seen.append((url,kwargs))
        if 'lawSearch' in url:
            data='<LawSearch><law><법령일련번호>12345</법령일련번호><현행연혁코드>현행</현행연혁코드><법령명한글>산업안전보건기준에 관한 규칙</법령명한글><시행일자>20260101</시행일자></law></LawSearch>'
        else:
            data='<법령><기본정보><법령명_한글>산업안전보건기준에 관한 규칙</법령명_한글></기본정보><조문><조문단위><조문번호>3</조문번호><조문여부>조문</조문여부><조문제목>전도의 방지</조문제목><조문내용>사업주는 작업장 바닥 등을 안전하게 유지하여야 한다.</조문내용></조문단위></조문></법령>'
        return httpx.Response(200,content=data.encode(),request=httpx.Request('GET',url))
    service=LawLinks('test-private-oc',get)
    verified=service.resolve('산업안전보건기준에 관한 규칙 제3조(전도의 방지)')
    assert verified[0]['verified'] and verified[0]['effective_date']=='20260101'
    assert seen[0][1]['params']['target']=='eflaw'
    assert 'test-private-oc' not in json.dumps(verified)
    assert service.resolve('산업안전보건기준에 관한 규칙 제3조(전도의 방지)')==verified and len(seen)==2
    mismatch=service.resolve('산업안전보건기준에 관한 규칙 제3조(다른 제목)')
    assert not mismatch[0]['verified']
