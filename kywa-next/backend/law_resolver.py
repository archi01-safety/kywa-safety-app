"""Official-source citation matching; all correction provenance stays server-side."""
import copy
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import OrderedDict
from urllib.parse import quote, urlencode, urlsplit

import httpx

VERSION = 'law-title-match-20261116-v2'
ALIASES = {'시특법': '시설물의 안전 및 유지관리에 관한 특별법',
           '시설물안전법': '시설물의 안전 및 유지관리에 관한 특별법'}
SEARCH = 'https://www.law.go.kr/lsSc.do?'
ARTICLE = re.compile(r'제\s*(\d+)\s*조(?:\s*의\s*(\d+))?'
    r'(?:\s*[（(]([^()（）]+)[)）])?(?:\s*제\s*(\d+)\s*항)?'
    r'(?:\s*제\s*(\d+)\s*호(?:\s*의\s*(\d+))?)?'
    r'(?:\s*[（(]([^()（）]+)[)）])?')


def safe_url(value):
    try:
        u = urlsplit(value)
        return u.scheme == 'https' and u.hostname in {'www.law.go.kr', 'law.go.kr'} and not u.username and not u.password and u.port in (None, 443) and not re.search(r'(?:^|&)(?:oc|key|token)=', u.query, re.I)
    except (TypeError, ValueError):
        return False


def compact(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text))


def title_key(text):
    return compact(text.strip().strip('()（）'))


def article_label(number, sub='', hang='', ho='', ho_sub='', title=''):
    return ('제' + number + '조' + ('의' + sub if sub else '') + ('(' + title + ')' if title else '')
            + (' 제' + hang + '항' if hang else '')
            + (' 제' + ho + '호' + ('의' + ho_sub if ho_sub else '') if ho else ''))


def citations(text):
    clean = re.sub(r'[「」『』]', ' ', text)  # Keep original offsets for precise replacements.
    results = []
    for part in re.finditer(r'[^;\n•]+', clean):
        matches = list(re.finditer(r'([가-힣][가-힣· ]*?(?:시행규칙|시행령|규칙|법률|법))(?!\s*시행(?:규칙|령))(?=\s|제|$|[,(:])', part[0]))
        for index, match in enumerate(matches):
            raw_name = re.sub(r'^(?:및|또는|관련근거|근거|법령)\s+', '', match[1].strip())
            name = ALIASES.get(raw_name, raw_name)
            if name.startswith(('KOSHA', '코샤')):
                continue
            start = part.start() + match.end()
            end = part.start() + (matches[index + 1].start() if index + 1 < len(matches) else len(part[0]))
            for a in list(ARTICLE.finditer(clean, start, end)) or [None]:
                number, sub = (a[1], a[2] or '') if a else ('', '')
                hang, ho, ho_sub = (a[4] or '', a[5] or '', a[6] or '') if a else ('', '', '')
                title = (a[3] or a[7] or '').strip() if a else ''
                name_start = part.start() + match.start() + match[0].find(raw_name)
                results.append({'key': (name, number, sub), 'name': name, 'number': number,
                    'sub': sub, 'title': title, 'hang': hang, 'ho': ho, 'ho_sub': ho_sub,
                    'label': name + (' ' + article_label(number, sub, hang, ho, ho_sub) if number else ''),
                    'span': (a.start(), a.end()) if a else None,
                    'name_span': (name_start, name_start + len(raw_name))})
    return results[:12]


def live_article(article):
    from .domain import now
    effective = re.sub(r'\D', '', article.findtext('조문시행일자', ''))
    if effective and (not re.fullmatch(r'\d{8}', effective) or effective > now()[:10].replace('-', '')):
        return False
    return (article.findtext('조문여부', '조문') == '조문' and not re.match(
        r'^\s*(?:제\d+조(?:의\d+)?\s*)?삭제(?:\s|<|\[|$)', article.findtext('조문내용', '')))


def numeric(value):
    return re.sub(r'\D', '', unicodedata.normalize('NFKC', value)).lstrip('0') or '0'


def subdivisions_exist(article, c):
    scope = article
    if c['hang']:
        parts = [p for p in article.findall('.//항') if numeric(p.findtext('항번호', '')) == c['hang']]
        if len(parts) != 1:
            return False
        scope = parts[0]
    if c['ho']:
        wanted = c['ho'] + ('의' + c['ho_sub'] if c['ho_sub'] else '')
        parts = [p for p in scope.findall('.//호') if re.sub(r'[\s.]', '', unicodedata.normalize('NFKC', p.findtext('호번호', ''))) == wanted]
        if len(parts) != 1:
            return False
    return True


class LawLinks:
    def __init__(self, oc='', get=None, referer=''):
        self.oc, self.get, self.referer = oc, get or httpx.get, referer
        self.cache, self.documents = OrderedDict(), OrderedDict()
        self.lock = threading.RLock()

    def _xml(self, endpoint, **params):
        response = self.get('https://www.law.go.kr/DRF/' + endpoint,
            params={'OC': self.oc, 'target': 'law', 'type': 'XML', **params}, timeout=8,
            headers={'User-Agent': 'KYWA-Safety/1.3', **({'Referer': self.referer} if self.referer else {})}, follow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 4 * 1024 * 1024 or b'<!DOCTYPE' in response.content.upper():
            raise ValueError()
        root = ET.fromstring(response.content)
        if root.tag == 'Response':
            raise ValueError('Official API rejected request parameters')
        return root

    def _document(self, endpoint, **params):
        key = (endpoint, tuple(sorted(params.items())))
        with self.lock:
            entry = self.documents.get(key)
            if entry and time.monotonic() - entry[0] < 3600:
                return entry[1]
            root = self._xml(endpoint, **params)
            self.documents[key] = (time.monotonic(), root)
            while len(self.documents) > 96:
                self.documents.popitem(last=False)
            return root

    def _verify(self, c):
        matches = self._document('lawSearch.do', target='eflaw', query=c['name'], search=1, display=30, nw=3)
        laws = [law for law in matches.findall('.//law') if compact(law.findtext('법령명한글', '')) == compact(c['name']) and law.findtext('현행연혁코드', '현행') == '현행']
        if len(laws) != 1:
            return None
        law = laws[0]
        identifier, effective = law.findtext('법령일련번호', ''), law.findtext('시행일자', '')
        from .domain import now
        if not identifier.isdigit() or not re.fullmatch(r'\d{8}', effective) or effective > now()[:10].replace('-', ''):
            return None
        params = dict(target='eflaw', MST=identifier, efYd=effective)
        number, sub, title = c['number'], c['sub'], c['title']
        if number and (len(number) > 4 or len(sub) > 2):
            return None
        body = self._document('lawService.do', **params, **({'JO': number.zfill(4) + (sub or '0').zfill(2)} if number else {}))
        if compact(body.findtext('.//법령명_한글', '')) != compact(c['name']):
            return None
        if number:
            articles = [a for a in body.findall('.//조문단위') if a.findtext('조문번호') == number and a.findtext('조문가지번호', '') in ((sub,) if sub else ('', '0')) and live_article(a)]
            if len(articles) != 1:  # Never silently revive a missing or deleted source article.
                return None
            article = articles[0]
            if title and title_key(title) != title_key(article.findtext('조문제목', '')):
                full = self._document('lawService.do', **params)
                if compact(full.findtext('.//법령명_한글', '')) != compact(c['name']):
                    return None
                candidates = [a for a in full.findall('.//조문단위') if live_article(a) and title_key(a.findtext('조문제목', '')) == title_key(title)]
                if len(candidates) != 1:
                    return None
                article = candidates[0]
                number, sub = article.findtext('조문번호', ''), article.findtext('조문가지번호', '')
                sub = '' if sub == '0' else sub
                if not number.isdigit() or (sub and not sub.isdigit()):
                    return None
            if not subdivisions_exist(article, c):
                return None
            title = article.findtext('조문제목', '').strip()
        canonical = article_label(number, sub, c['hang'], c['ho'], c['ho_sub'], title) if number else ''
        url = 'https://www.law.go.kr/법령/' + quote(compact(c['name']), safe='')
        published, published_no = law.findtext('공포일자', ''), re.sub(r'\D', '', law.findtext('공포번호', ''))
        if published_no and re.fullmatch(r'\d{8}', published):
            url += '/(' + effective + ',' + published_no + ',' + published + ')'
        if number:
            url += '/' + quote(article_label(number, sub, c['hang'], c['ho'], c['ho_sub']).replace(' ', ''), safe='')
        return {'label': c['name'] + (' ' + canonical if canonical else ''), 'url': url,
                'verified': True, 'effective_date': effective,
                'message': '공식 원문 확인 · 현장 적합성 판정과는 별도', '_canonical': canonical}

    def resolve_text(self, text):
        result, replacements, audits = [], {}, []
        for c in citations(text):
            key = (*c['key'], c['title'], c['hang'], c['ho'], c['ho_sub'])
            with self.lock:
                entry = self.cache.get(key)
            value = copy.deepcopy(entry[1]) if entry and time.monotonic() - entry[0] < (3600 if entry[1]['verified'] else 60) else None
            if value is None:
                if self.oc:
                    try:
                        value = self._verify(c)
                    except Exception:
                        pass  # Provider exceptions can contain credentials; never expose/log them.
                if not value:
                    value = {'label': c['label'], 'url': SEARCH + urlencode({'query': c['label']}),
                             'verified': False, 'effective_date': '', 'message': '조문 원문 확인 필요 · 공식 법령 검색'}
                with self.lock:
                    self.cache[key] = (time.monotonic(), copy.deepcopy(value))
                    while len(self.cache) > 256:
                        self.cache.popitem(last=False)
            canonical = value.pop('_canonical', '')
            if value['verified'] and c['span'] and canonical:
                start, end = c['span']
                if text[start:end] != canonical:
                    replacements[(start, end)] = canonical
                    audits.append({'from': text[start:end], 'to': canonical, 'effective_date': value['effective_date']})
            if value['verified']:
                start, end = c['name_span']
                if text[start:end] != c['name']:
                    replacements[(start,end)] = c['name']
                    audits.append({'from':text[start:end], 'to':c['name'], 'effective_date':value['effective_date']})
            if value not in result:
                result.append(value)
        final = text
        for (start, end), value in sorted(replacements.items(), reverse=True):
            final = final[:start] + value + final[end:]
        return {'text': final, 'items': result, '_internal_law': {'version': VERSION, 'changes': audits} if audits else None}

    def resolve(self, text):
        return self.resolve_text(text)['items']

    def enrich(self, item):
        value = copy.deepcopy(item)
        resolved = self.resolve_text(value.get('law', ''))
        value.update(law=resolved['text'], law_references=resolved['items'])
        if resolved['_internal_law']:
            value['_internal_law'] = resolved['_internal_law']
        return value


def references(record):
    before = record.get('before', record)
    refs = before.get('law_references') or LawLinks().resolve(before.get('law', ''))
    return [r for r in refs if safe_url(r.get('url', ''))]


def verified_records(records, service):
    result = copy.deepcopy(records)
    texts = {r['before'].get('law', '') for r in result}
    resolved = {t: service.resolve_text(t) if hasattr(service, 'resolve_text') else {'text': t, 'items': service.resolve(t)} for t in texts}
    for record in result:
        value = resolved[record['before'].get('law', '')]
        record['before'].update(law=value['text'], law_references=copy.deepcopy(value['items']))
    return result
