"""Validated, deployment-local policy. No process-global tenant selection."""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from .submitter_name import is_masked_name


class PolicyError(ValueError):
    pass


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Level(Model):
    value: StrictInt = Field(ge=1, le=10)
    description: str = Field(min_length=1, max_length=500)


class Grade(Model):
    name: str = Field(min_length=1, max_length=40)
    tone: StrictInt = Field(ge=0, le=5)
    urgent: bool = False


class Cell(Model):
    p: StrictInt
    s: StrictInt
    score: StrictInt = Field(ge=0, le=10000)
    grade: str


class Policy(Model):
    version: str = Field(min_length=1, max_length=100)
    method: Literal['product', 'matrix'] = 'product'
    p_levels: list[Level] = Field(min_length=1, max_length=10)
    s_levels: list[Level] = Field(min_length=1, max_length=10)
    grades: list[Grade] = Field(min_length=1, max_length=12)
    cells: list[Cell] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def complete_matrix(self):
        ps, ss = [x.value for x in self.p_levels], [x.value for x in self.s_levels]
        names = [x.name for x in self.grades]
        pairs = [(x.p, x.s) for x in self.cells]
        if len(set(ps)) != len(ps) or len(set(ss)) != len(ss) or len(set(names)) != len(names):
            raise ValueError('평가 단계와 등급 이름은 중복될 수 없습니다.')
        if len(set(pairs)) != len(pairs) or set(pairs) != {(p, s) for p in ps for s in ss}:
            raise ValueError('모든 빈도·강도 조합을 한 번씩 정의하세요.')
        if any(c.grade not in names or (self.method == 'product' and c.score != c.p*c.s) for c in self.cells):
            raise ValueError('평가표의 점수 또는 등급이 잘못되었습니다.')
        return self

    def risk(self, p, s):
        cell = next((c for c in self.cells if c.p == p and c.s == s), None)
        if type(p) is not int or type(s) is not int or cell is None:
            raise PolicyError('기관 평가 기준에 없는 빈도·강도입니다.')
        grade = next(g for g in self.grades if g.name == cell.grade)
        return dict(p=p, s=s, score=cell.score, grade=cell.grade, tone=grade.tone, urgent=grade.urgent)

    def prompt(self):
        return ('적용 평가 기준: ' + self.version + '\n빈도 p: ' +
                '; '.join(f'{x.value}({x.description})' for x in self.p_levels) + '\n강도 s: ' +
                '; '.join(f'{x.value}({x.description})' for x in self.s_levels) +
                '\n허용된 단계만 선택한다. 점수·등급은 서버의 평가표에서 산정한다.')


class NameField(Model):
    mode: Literal['disabled', 'optional', 'required'] = 'disabled'
    label: str = Field(default='제출자 성명', min_length=1, max_length=40)
    notice: str = Field(default='', max_length=1000)
    show_in_reports: bool = False


class Branding(Model):
    primary: str = Field(default='#64748B', pattern=r'^#[0-9A-Fa-f]{6}$')
    logo: str = Field(default='', pattern=r'^(|/[A-Za-z0-9_./-]+\.(png|svg|webp))$')
    website: str = ''
    department: str = ''
    email: str = ''
    phone: str = ''


class Storage(Model):
    spreadsheet_id: str = Field(default='', pattern=r'^[A-Za-z0-9_-]*$')
    drive_folder_id: str = Field(default='', pattern=r'^[A-Za-z0-9_-]*$')
    sheet_name: str = '시트1'
    expected_service_account: str = 'kywa-safety-check@gen-lang-client-0053629470.iam.gserviceaccount.com'
    legacy_name_column: bool = False


class Organization(Model):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    demo_only: bool = False
    name: str = Field(min_length=1, max_length=100)
    short_name: str = Field(min_length=1, max_length=40)
    facilities: list[str] = Field(min_length=1)
    departments: list[str] = Field(min_length=1)
    categories: list[str] = Field(min_length=1)
    category_guidance: str = ''
    prompt_version: str = Field(min_length=1, max_length=100)
    prompt_guidance: str = ''
    submitter_name: NameField = Field(default_factory=NameField)
    branding: Branding = Field(default_factory=Branding)
    storage: Storage = Field(default_factory=Storage)
    source: dict = Field(default_factory=dict)
    policy: Policy

    @model_validator(mode='after')
    def validate_lists(self):
        for values in (self.facilities, self.departments, self.categories):
            if any(not x.strip() or x != x.strip() or len(x) > 100 for x in values) or len(set(values)) != len(values):
                raise ValueError('기관 목록에는 중복 또는 빈 값을 사용할 수 없습니다.')
        if any(len(c) > 40 for c in self.categories):
            raise ValueError('위험 분류는 40자 이하여야 합니다.')
        return self

    def name_value(self, value):
        if self.submitter_name.mode == 'disabled':
            if value:
                raise PolicyError('이 기관은 성명을 수집하지 않습니다.')
            return ''
        if self.submitter_name.mode == 'required' and not value:
            raise PolicyError(f'{self.submitter_name.label}을 입력하세요.')
        if value and not is_masked_name(value):
            raise PolicyError('성명은 첫 글자와 초성으로 변환된 형식만 제출할 수 있습니다.')
        return value


def load_organization(organization_id, directory=None):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', organization_id):
        raise ValueError('ORGANIZATION_ID 형식이 잘못되었습니다.')
    path = Path(directory or Path(__file__).parent / 'organizations') / f'{organization_id}.json'
    if not path.is_file():
        raise ValueError(f'기관 설정 파일이 없습니다: {organization_id}')
    org = Organization.model_validate_json(path.read_text(encoding='utf-8'))
    if org.id != organization_id:
        raise ValueError('기관 설정 ID와 파일명이 다릅니다.')
    if org.id == 'kywa' and org.policy.version == 'KYWA-2026-6LEVEL-v1':
        frozen = Policy.model_validate_json((Path(__file__).parent / 'policies' / 'kywa-v1.json').read_text(encoding='utf-8'))
        if org.policy != frozen:
            raise ValueError('KYWA v1은 보존된 기준입니다. 기준 변경 시 새 버전을 부여하세요.')
    return org


def record_policy(record, org):
    if record.get('legacy_source') == 'streamlit' and record.get('reassessment_policy_snapshot'):
        return Policy.model_validate(record['reassessment_policy_snapshot'])
    snapshot = record.get('policy_snapshot')
    if snapshot:
        policy = Policy.model_validate(snapshot)
        if policy.version != record['policy']:
            raise PolicyError('기록의 평가 기준 버전이 일치하지 않습니다.')
        return policy
    if org.id == 'kywa' and record['policy'] == 'KYWA-2026-6LEVEL-v1':
        return Policy.model_validate_json((Path(__file__).parent / 'policies' / 'kywa-v1.json').read_text(encoding='utf-8'))
    if record['policy'] == org.policy.version:
        return org.policy
    raise PolicyError('이 기록의 원래 평가 기준이 확인되지 않아 재평가할 수 없습니다. 기준 이관이 필요합니다.')
