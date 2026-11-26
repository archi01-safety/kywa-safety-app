"""Build traceable, synthetic institution profiles; no production records are inputs."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.organization import load_organization
from backend.detailed_risk import FACTS

ORGS = ('kywa', 'ayf', 'fowi', 'khidi', 'knps', 'knf', 'kohi', 'cayf')


def build():
    folder = ROOT / 'backend' / 'risk_profiles'
    folder.mkdir(exist_ok=True)
    for org_id in ORGS:
        org = load_organization(org_id)
        source = {'policy': org.policy.model_dump(), 'prompt': org.prompt_version}
        profile = {'schema': 1, 'organization': org_id, 'version': org_id + '-facts-20261116-v3',
            'policy_version': org.policy.version, 'source_sha256': hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'source': {'policy_version': org.policy.version, 'prompt_version': org.prompt_version,
                'frequency': [x.model_dump() for x in org.policy.p_levels], 'severity': [x.model_dump() for x in org.policy.s_levels]},
            'weights': {field: {k: v for k, _, v in options} for field, (_, options) in FACTS.items()},
            'defaults': {'exposure': 'daily', 'contact': 'possible', 'controls': 'ineffective', 'condition': 'degrading', 'consequence': 'lost_time', 'extent': 'moderate'},
            'minor_cap': 4 if org_id == 'fowi' else 5 if org_id == 'khidi' else 6,
            'quantitative_rules': org_id == 'fowi',
            'question_labels': {'exposure': '평소 얼마나 자주 이용하거나 작업하나요?', 'contact': '위험 부위에 직접 닿을 수 있나요?',
                'controls': '위험을 막는 장치나 조치가 있나요?', 'condition': '위험한 상태가 계속되거나 반복되나요?',
                'consequence': '사고가 나면 어느 정도 다칠 수 있나요?', 'extent': '예상되는 피해 범위는 어느 정도인가요?'},
            'likelihood_levels': [{'internal':(level.value-1)*3+sub,'public':level.value,
                'position':('하단','중간','상단')[sub-1],'basis':level.description} for level in org.policy.p_levels for sub in (1,2,3)],
            'severity_levels': [{'internal':(level.value-1)*5+sub,'public':level.value,
                'position':('매우 제한적','제한적','보통','넓은 범위','매우 넓은 범위')[sub-1],'basis':level.description} for level in org.policy.s_levels for sub in (1,2,3,4,5)],
            'limitations': 'Synthetic policy alignment and repeatability only; not expert accuracy certification.'}
        profile['algorithm_sha256']=hashlib.sha256((ROOT/'backend/risk_profiles.py').read_bytes()).hexdigest()
        profile['profile_sha256']=hashlib.sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        (folder / (org_id + '.json')).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'profiles': len(ORGS), 'date': '2026-11-16'}))


if __name__ == '__main__':
    build()
