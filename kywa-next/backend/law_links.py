"""Official-source citation lookup; provider keys and untrusted URLs never leave the server."""
import copy
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from urllib.parse import quote, urlencode, urlsplit

import httpx

ALIASES = {'시특법':'시설물의 안전 및 유지관리에 관한 특별법',
           '시설물안전법':'시설물의 안전 및 유지관리에 관한 특별법'}
SEARCH = 'https://www.law.go.kr/lsSc.do?'


def safe_url(value):
    try:
        url = urlsplit(value)
        return url.scheme=='https' and url.hostname in {'www.law.go.kr','law.go.kr'} and not url.username and not url.password and url.port in (None,443) and not re.search(r'(?:^|&)(?:oc|key|token)=',url.query,re.I)
    except (TypeError,ValueError):
        return False


def compact(text):
    return re.sub(r'\s+','',text)


def citations(text):
    results=[]
    for part in re.split(r'[;\n•]+',text):
        clean=re.sub(r'[「」『』]','',part)
        matches=list(re.finditer(r'([가-힣][가-힣· ]*?(?:시행규칙|시행령|규칙|법률|법))(?=\s|제|$|[,(:])',clean))
        for index,match in enumerate(matches):
            name=re.sub(r'^(?:및|또는|관련근거|근거|법령)\s+','',match[1].strip()); name=ALIASES.get(name,name)
            if name.startswith(('KOSHA','코샤')): continue
            tail=clean[match.end():matches[index+1].start() if index+1<len(matches) else len(clean)]
            articles=list(re.finditer(r'제\s*(\d+)\s*조(?:\s*의\s*(\d+))?(?:\s*\(([^)]+)\))?',tail))
            for article in articles or [None]:
                key=(name,article[1] if article else '',article[2] or '' if article else '')
                if key in {r['key'] for r in results}: continue
                results.append({'key':key,'name':name,'number':key[1],'sub':key[2],
                    'title':article[3] or '' if article else '',
                    'label':name+((' 제'+key[1]+'조'+('의'+key[2] if key[2] else '')) if article else '')})
    return results[:12]


class LawLinks:
    def __init__(self, oc='', get=None):
        self.oc,self.get=oc,get or httpx.get
        self.cache=OrderedDict(); self.lock=threading.RLock()

    def _xml(self, endpoint, **params):
        response=self.get('https://www.law.go.kr/DRF/'+endpoint,
            params={'OC':self.oc,'target':'law','type':'XML',**params},timeout=8,
            headers={'User-Agent':'KYWA-Safety/1.1','Referer':'https://www.law.go.kr/'},follow_redirects=False)
        response.raise_for_status()
        if len(response.content)>4*1024*1024 or b'<!DOCTYPE' in response.content.upper(): raise ValueError()
        return ET.fromstring(response.content)

    def _verify(self,citation):
        matches=self._xml('lawSearch.do',target='eflaw',query=citation['name'],search=1,display=30,nw=3)
        laws=[law for law in matches.findall('.//law') if compact(law.findtext('법령명한글',''))==compact(citation['name']) and law.findtext('현행연혁코드','현행')=='현행']
        if len(laws)!=1: return None
        law=laws[0]; identifier=law.findtext('법령일련번호','')
        effective=law.findtext('시행일자','')
        from .domain import now
        if not identifier.isdigit() or not re.fullmatch(r'\d{8}',effective) or effective>now()[:10].replace('-',''): return None
        body=self._xml('lawService.do',target='eflaw',MST=identifier,efYd=effective)
        if compact(body.findtext('.//법령명_한글',''))!=compact(citation['name']): return None
        if citation['number']:
            articles=[a for a in body.findall('.//조문단위') if a.findtext('조문번호')==citation['number']
                      and a.findtext('조문가지번호','') in ((citation['sub'],) if citation['sub'] else ('','0'))]
            if len(articles)!=1: return None
            article=articles[0]
            if '삭제' in article.findtext('조문내용',''): return None
            if citation['title'] and compact(citation['title'])!=compact(article.findtext('조문제목','')): return None
        url='https://www.law.go.kr/법령/'+quote(compact(citation['name']),safe='')+'/('+effective+')'
        if citation['number']: url+='/'+quote('제'+citation['number']+'조'+('의'+citation['sub'] if citation['sub'] else ''),safe='')
        return {'label':citation['label'],'url':url,'verified':True,'effective_date':effective,'message':'공식 원문 확인 · 현장 적합성 판정과는 별도'}

    def resolve(self,text):
        result=[]
        for citation in citations(text):
            key=(self.oc,*citation['key'],citation['title'])
            with self.lock:
                cached=self.cache.get(key)
            if cached and time.monotonic()-cached[0]<3600:
                result.append(copy.deepcopy(cached[1]));continue
            value=None
            if self.oc:
                try: value=self._verify(citation)
                except Exception: pass  # No provider URL/error text (OC) in logs or client output.
            if not value:
                value={'label':citation['label'],'url':SEARCH+urlencode({'query':citation['label']}),
                       'verified':False,'effective_date':'','message':'조문 원문 확인 필요 · 공식 법령 검색'}
            with self.lock:
                self.cache[key]=(time.monotonic(),copy.deepcopy(value))
                while len(self.cache)>256: self.cache.popitem(last=False)
            result.append(value)
        return result


def references(record):
    before=record.get('before',record)
    refs=before.get('law_references') or LawLinks().resolve(before.get('law',''))
    return [r for r in refs if safe_url(r.get('url',''))]
