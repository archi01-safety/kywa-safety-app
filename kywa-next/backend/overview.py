"""Public counts only; never return evaluation text, identities or photo links."""
from collections import Counter

from .domain import FACILITIES, CATEGORIES


def summarize(records, year):
    years = sorted({int(r['created_at'][:4]) for r in records
                    if str(r.get('created_at', ''))[:4].isdigit()} | {year}, reverse=True)
    selected = [r for r in records if str(r.get('created_at', '')).startswith(f'{year}-')]
    facilities = Counter(r['facility'] if r['facility'] in FACILITIES else '기타' for r in selected)
    categories = Counter(r['before']['category'] if r['before']['category'] in CATEGORIES else '기타'
                         for r in selected)
    return dict(year=year, years=years, total=len(selected),
                completed=sum(r['status'] == '완료' for r in selected),
                facility_count=len(facilities),
                facilities=[dict(name=f, count=facilities[f]) for f in FACILITIES + (['기타'] if facilities['기타'] else [])],
                categories=[dict(name=k, count=v) for k, v in categories.most_common()])


def guide_keywords(items):
    # Preserve the original rule order, considering all analysis items rather than just the first.
    words = ['용접', '비계', '사다리', '지게차', '크레인', '개구부', '난간', '추락', '감전', '화재',
             '전기', '미끄러짐', '넘어짐', '중량물', '화학물질', '소음', '밀폐공간', '보호구']
    text = ' '.join(str(item.get(key, '')) for item in items for key in ('scenario', 'law', 'solution'))
    return [word for word in words if word in text][:3]
