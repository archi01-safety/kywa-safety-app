"""Versioned, deterministic 15-by-20 assessment draft rules."""
from copy import deepcopy
from typing import Literal

from pydantic import Field

from .domain import StrictModel

VERSION = 'risk-facts-2026-11-12-v1'
FACTS = {
    'exposure': ('이용·작업 빈도를 확인해 주세요', [
        ('rare', '드물게 이용·작업', 0), ('monthly', '월 단위', 1),
        ('daily', '일 단위', 2), ('continuous', '상시·반복', 3)]),
    'contact': ('사고 원인에 접촉할 가능성을 확인해 주세요', [
        ('isolated', '위험원과 분리됨', 0), ('unlikely', '접촉 가능성이 낮음', 1),
        ('possible', '부주의하면 접촉 가능', 3), ('likely', '접촉 가능성이 높음', 4),
        ('direct', '위험에 직접 노출됨', 5)]),
    'controls': ('현재 안전조치를 확인해 주세요', [
        ('effective', '효과적인 조치가 확인됨', 0), ('partial', '일부 조치만 확인됨', 2),
        ('ineffective', '조치가 있으나 효과 부족', 3), ('none', '조치 없음이 확인됨', 4)]),
    'condition': ('위험 상태를 확인해 주세요', [
        ('stable', '위험 상태가 확대되지 않음', 0), ('degrading', '상태가 악화되고 있음', 1),
        ('repeated', '노출·위험 상황이 반복됨', 2)]),
    'consequence': ('예상되는 피해를 확인해 주세요', [
        ('minor', '경미한 부상', 0), ('first_aid', '응급처치 이상·비휴업', 1),
        ('lost_time', '중대한 부상·휴업', 2), ('fatal', '사망·영구 장애', 3)]),
    'extent': ('예상 피해의 범위를 확인해 주세요', [
        ('very_limited', '매우 제한적', 1), ('limited', '제한적', 2),
        ('moderate', '보통', 3), ('extensive', '넓은 범위', 4), ('critical', '매우 넓은 범위', 5)]),
}


class Observation(StrictModel):
    category: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=1, max_length=2000)
    law: str = Field(default='', max_length=2000)
    solution: str = Field(min_length=1, max_length=3000)
    exposure: Literal['rare', 'monthly', 'daily', 'continuous', 'unknown']
    contact: Literal['isolated', 'unlikely', 'possible', 'likely', 'direct', 'unknown']
    controls: Literal['effective', 'partial', 'ineffective', 'none', 'unknown']
    condition: Literal['stable', 'degrading', 'repeated', 'unknown']
    consequence: Literal['minor', 'first_aid', 'lost_time', 'fatal', 'unknown']
    extent: Literal['very_limited', 'limited', 'moderate', 'extensive', 'critical', 'unknown']


class Observations(StrictModel):
    items: list[Observation] = Field(min_length=1, max_length=12)


class FactAnswer(StrictModel):
    index: int = Field(ge=0, le=11)
    field: str = Field(max_length=20)
    value: str = Field(max_length=30)


class ConfirmFacts(StrictModel):
    answers: list[FactAnswer] = Field(max_length=72)


def allowed(field):
    return {key: value for key, _, value in FACTS[field][1]}


def calculate(likelihood,severity,policy,minor=False):
    if type(likelihood) is not int or not 1<=likelihood<=15 or type(severity) is not int or not 1<=severity<=20:
        raise ValueError('관찰 판정 범위를 확인하세요.')
    p,s=(likelihood+2)//3,(severity+4)//5
    cap=4 if policy.version.lower().startswith('fowi') else 5 if policy.version.lower().startswith('khidi') else 6
    # A minor-damage cap never applies to potentially fatal/major injuries.
    if minor and s<=2:
        while p*s>cap:p-=1
        likelihood=min(likelihood,p*3)
    return policy.risk(p,s),likelihood,severity


def resolve(observations, policy, answers=()):
    values = deepcopy(observations)
    seen = set()
    for answer in answers:
        key = (answer.index, answer.field)
        if (key in seen or answer.index >= len(values) or answer.field not in FACTS
                or answer.value not in allowed(answer.field)):
            raise ValueError('추가 확인 응답의 형식이 올바르지 않습니다.')
        seen.add(key)
        if values[answer.index][answer.field] != 'unknown':
            raise ValueError('확인 대상이 변경되었습니다. 현재 질문을 다시 확인해 주세요.')
        values[answer.index][answer.field] = answer.value
    questions, results = [], []
    for index, facts in enumerate(values):
        for field, (label, options) in FACTS.items():
            if facts[field] == 'unknown':
                questions.append({'index': index, 'field': field, 'label': label,
                                  'location': facts['location'],
                                  'options': [{'value': key, 'label': text} for key, text, _ in options]})
        if any(facts[field] == 'unknown' for field in FACTS):
            continue
        likelihood = 1 + sum(allowed(field)[facts[field]] for field in
                             ('exposure', 'contact', 'controls', 'condition'))
        severity = 5 * allowed('consequence')[facts['consequence']] + allowed('extent')[facts['extent']]
        minor=(facts['category'] in ('시설 안전','보행 안전') and facts['consequence'] in ('minor','first_aid')
               and facts['extent'] in ('very_limited','limited') and facts['condition']=='stable'
               and facts['contact'] not in ('direct','likely'))
        original_likelihood=likelihood
        calculated,likelihood,severity=calculate(likelihood,severity,policy,minor)
        item = {field: facts[field] for field in ('category', 'location', 'scenario', 'law', 'solution')}
        item.update(calculated)
        item['_internal_risk'] = {
            'version': VERSION, 'likelihood': likelihood, 'severity': severity,
            'score': likelihood * severity, 'minor_cap_applied':likelihood!=original_likelihood,
            'facts': {field: facts[field] for field in FACTS},
        }
        results.append(item)
    return values, questions, results


def public_item(item):
    return {key: value for key, value in item.items() if not key.startswith('_internal')}
