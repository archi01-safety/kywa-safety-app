"""Institution-owned refinements of the published matrix, never a 300/20 rescaling."""
import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from .detailed_risk import FACTS, calculate

ROOT = Path(__file__).parent / 'risk_profiles'
CRITICAL = {'fall_from_height', 'electric_shock', 'entanglement', 'fire_explosion', 'collapse'}
MECHANISMS = {
    'fall_from_height': (r'고소|옥상|높이|추락|개구부', r'추락|난간.*(?:없|미설치)|안전대.*(?:없|미착용)'),
    'electric_shock': (r'활선|충전부|통전|누전', r'감전|접촉|노출|닿'),
    'entanglement': (r'가동|구동|회전', r'끼임|말림|협착'),
    'fire_explosion': (r'폭발|가연성.*(?:증기|가스)|인화성', r'점화|누출|밀폐|축적|폭발'),
    'collapse': (r'붕괴|무너|매몰', r'축대|토사|구조물|건물|비계|옹벽'),
}


@lru_cache(maxsize=32)
def load_profile(policy_version):
    organization = policy_version.split('-')[0].lower()
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', organization):
        raise ValueError('세부 기준의 기관 식별자를 확인하세요.')
    path = ROOT / (organization + '.json')
    if not path.is_file():
        raise ValueError('이 기관의 검증된 세부 기준이 준비되지 않았습니다.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if value['organization'] != organization or value['policy_version'] != policy_version:
        raise ValueError('세부 기준과 기관 평가표의 버전이 다릅니다.')
    return value


def profile_version(policy):
    return load_profile(policy.version)['version']


def _measured(value, field, evidence_text):
    """Use only quantities explicitly stated with their units, not model guesses."""
    number = value.get(field)
    if number is None:
        return None
    patterns = {'exposure_percent': r'(\d+(?:\.\d+)?)\s*%',
                'daily_hours': r'(\d+(?:\.\d+)?)\s*시간',
                'noise_db': r'(\d+(?:\.\d+)?)\s*d[Bb]'}
    found = [float(n) for n in re.findall(patterns[field], evidence_text)]
    return number if number in found else None


def evaluate(facts, policy, profile, evidence_text=''):
    effective = copy.deepcopy(facts)
    defaults = {}
    for field in FACTS:
        if effective[field] == 'unknown':
            effective[field] = profile['defaults'][field]
            defaults[field] = effective[field]
    weights = profile['weights']
    likelihood = 1 + sum(weights[field][effective[field]] for field in ('exposure', 'contact', 'controls', 'condition'))
    severity = 5 * weights['consequence'][effective['consequence']] + weights['extent'][effective['extent']]
    rules = []
    hazard = facts.get('hazard', 'general')
    mechanism_text = facts.get('scenario', '') + ' ' + evidence_text
    credible_mechanism = hazard in MECHANISMS and all(re.search(pattern, mechanism_text) for pattern in MECHANISMS[hazard])
    if credible_mechanism and facts.get('hazard_active') is True and effective['contact'] != 'isolated':
        # Protective measures reduce likelihood; they do not turn a credible fatal injury into a minor one.
        severity = max(severity, 16)
        rules.append('credible_fatal_consequence')
    if profile['quantitative_rules']:
        ratio = _measured(facts, 'exposure_percent', evidence_text)
        hours = _measured(facts, 'daily_hours', evidence_text)
        noise = _measured(facts, 'noise_db', evidence_text)
        if hazard == 'chemical' and ratio is not None:
            p = 1 + sum(ratio >= boundary for boundary in (10, 40, 70, 100))
            likelihood = (p - 1) * 3 + 2
            rules.append('fowi_measured_exposure')
        if hazard == 'ergonomic' and hours is not None and hours > 0:
            p = 5 if hours >= 8 else 4 if hours >= 4 else 3
            likelihood = max(likelihood, (p - 1) * 3 + 2)
            rules.append('fowi_reported_daily_hours')
        if hazard == 'noise' and noise is not None:
            s = 4 if noise >= 90 else 3 if noise >= 85 else 2 if noise >= 80 else 1
            severity = (s - 1) * 5 + 3
            rules.append('fowi_reported_noise')
        if hazard == 'ergonomic' and facts.get('ergonomic_effort') in ('moderate', 'hard', 'very_hard'):
            s = {'moderate': 2, 'hard': 3, 'very_hard': 4}[facts['ergonomic_effort']]
            severity = max(severity, (s - 1) * 5 + 3)
            rules.append('fowi_reported_effort')
    minor = (facts['category'] in ('시설 안전', '보행 안전') and hazard == 'general'
        and effective['consequence'] in ('minor', 'first_aid') and effective['extent'] in ('very_limited', 'limited')
        and effective['condition'] == 'stable' and effective['contact'] not in ('direct', 'likely')
        and not any(field in defaults for field in ('consequence', 'condition', 'contact')))
    original = likelihood
    result, likelihood, severity = calculate(likelihood, severity, policy, minor, minor_cap=profile['minor_cap'])
    result['_internal_risk'] = {'version': profile['version'], 'profile_sha256': profile['profile_sha256'],
        'likelihood': likelihood, 'severity': severity, 'score': likelihood * severity,
        'minor_cap_applied': original != likelihood, 'facts': copy.deepcopy(facts),
        'defaulted_facts': defaults, 'rules': rules, 'policy_version': policy.version}
    return result


def resolve_optional(observations, policy, answers=(), *, evidence_text=''):
    profile = load_profile(policy.version)
    values = copy.deepcopy(observations)
    seen = set()
    for answer in answers:
        key = (answer.index, answer.field)
        valid = {x[0] for x in FACTS.get(answer.field, ('', []))[1]} | {'unknown'}
        if key in seen or answer.index >= len(values) or answer.field not in FACTS or answer.value not in valid:
            raise ValueError('현재 초안의 선택 항목을 확인해 주세요.')
        seen.add(key)
        if values[answer.index][answer.field] != 'unknown':
            raise ValueError('추가 확인 대상이 아닙니다.')
        values[answer.index][answer.field] = answer.value
    candidates, results = [], []
    for index, facts in enumerate(values):
        result = evaluate(facts, policy, profile, evidence_text)
        for field, (label, options) in FACTS.items():
            if facts[field] != 'unknown':
                continue
            variants = []
            for key, _, _ in options:
                changed = {**facts, field: key}
                variants.append(evaluate(changed, policy, profile, evidence_text))
            tones = [r['tone'] for r in variants]
            if len({r['grade'] for r in variants}) < 2:
                continue
            # At most two high-impact, easy choices for the entire analysis, not two per finding.
            priority = (max(tones) - min(tones), field == 'consequence', max(r['score'] for r in variants) - min(r['score'] for r in variants))
            question = {'index': index, 'field': field, 'label': profile['question_labels'].get(field, label),
                'location': facts['location'], 'options': [{'value': k, 'label': t} for k, t, _ in options] + [{'value': 'unknown', 'label': '잘 모르겠어요'}]}
            candidates.append((priority, question))
        item = {field: facts[field] for field in ('category', 'location', 'scenario', 'law', 'solution')}
        item.update(result)
        results.append(item)
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return values, [q for _, q in candidates[:2]], results
