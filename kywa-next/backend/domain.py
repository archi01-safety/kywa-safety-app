import hashlib
import json
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

FACILITIES = ['중앙', '평창', '우주', '바이오', '해양', '미래', '생태', '본원']
DEPARTMENTS = ['협력부(국립청소년시설)', '활동부(국립청소년시설)', '근로자대표', '청소년성장지원부',
               '지도인력양성부', '지도인력개발부', '청렴감사실', '기획혁신부', '인재경영부',
               '홍보전략부', '안전경영부', '재무회계부', '디지털정보부', '활동기획부', '미래활동부',
               '정책사업부', '활동안전부', '활동인증부', '자회사', '협력업체(공사, 용역 등)']
CATEGORIES = ['보행 안전', '시설 안전', '화재 안전', '작업 안전', '활동 안전', '보건 및 위생관리',
              '화학물질 관리', '작업 환경', '작업 특성', '기계(설비)적 요인', '전기적 요인', '재난 안전']
POLICY = 'KYWA-2026-6LEVEL-v1'
HEADERS = ['타임스탬프', '시설명', '담당 부서', '장소', '유해위험요인', '위험상황', '빈도', '강도',
           '점수', '위험등급', '감소대책', '관련근거', '사진 기록', '개선후 빈도', '개선후 강도',
           '개선후 점수', '개선후 위험등급', '개선후 사진기록', '평가ID', '평가기준버전', '처리상태',
           '수정버전', '시스템데이터']
HISTORY_HEADERS = ['조치ID', '평가ID', '처리시각', '처리자', '작업', '조치내용', '시스템데이터']


def now():
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')


def risk(p: int, s: int):
    if type(p) is not int or type(s) is not int or not 1 <= p <= 5 or not 1 <= s <= 4:
        raise ValueError('빈도 1~5, 강도 1~4의 정수를 입력하세요.')
    score = p * s
    grade = ('매우 낮음' if score <= 3 else '낮음' if score <= 6 else '보통' if score == 8
             else '약간 높음' if score <= 12 else '높음' if score == 15 else '매우 높음')
    return {'p': p, 's': s, 'score': score, 'grade': grade}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class RiskInput(StrictModel):
    category: str = Field(max_length=40)
    location: str = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=1, max_length=2000)
    p: StrictInt = Field(ge=1, le=5)
    s: StrictInt = Field(ge=1, le=4)
    law: str = Field(default='', max_length=2000)
    solution: str = Field(min_length=1, max_length=3000)

    @field_validator('category')
    @classmethod
    def known_category(cls, value):
        if value not in CATEGORIES:
            raise ValueError('허용되지 않은 위험 분류입니다.')
        return value


class RiskList(StrictModel):
    items: list[RiskInput] = Field(min_length=1, max_length=12)


class AfterRisk(StrictModel):
    p: StrictInt = Field(ge=1, le=5)
    s: StrictInt = Field(ge=1, le=4)
    rationale: str = Field(min_length=1, max_length=2000)


class EditedRisk(StrictModel):
    index: StrictInt = Field(ge=0, le=11)
    location: str = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=1, max_length=2000)
    solution: str = Field(min_length=1, max_length=3000)


class SubmitRequest(StrictModel):
    request_id: str = Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    draft_id: str
    items: list[EditedRisk] = Field(min_length=1, max_length=12)


class ActionRequest(StrictModel):
    request_id: str = Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    draft_id: str
    revision: StrictInt = Field(ge=1)
    p: StrictInt = Field(ge=1, le=5)
    s: StrictInt = Field(ge=1, le=4)
    complete: bool = True


class StateRequest(StrictModel):
    request_id: str = Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    revision: StrictInt = Field(ge=1)
    status: Literal['조치 중', '접수']


class ReportRequest(StrictModel):
    format: Literal['xlsx', 'pdf']
    facility: str = ''
    department: str = ''
    status: str = ''
    start: str = ''
    end: str = ''


def sheet_row(record):
    b, a = record['before'], record.get('after') or {}
    photo = lambda fid: f'https://drive.google.com/file/d/{fid}/view' if fid else '사진 없음'
    values = [record['created_at'], record['facility'], record['department'], b['location'], b['category'],
            b['scenario'], b['p'], b['s'], b['score'], b['grade'], b['solution'], b['law'], photo(record.get('photo_id')),
            a.get('p', ''), a.get('s', ''), a.get('score', ''), a.get('grade', ''), photo(a.get('photo_id')),
            record['id'], record['policy'], record['status'], record['revision'],
            json.dumps(record, ensure_ascii=False, separators=(',', ':'))]
    if record.get('legacy_values'):
        values[:13] = record['legacy_values'][:13]
    return values
