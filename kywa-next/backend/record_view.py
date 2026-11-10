import copy
from .organization import record_policy
from .submitter_name import display_name

def public_record(record, org, cfg):
    r = copy.deepcopy(record)
    for key in list(r):
        if key.startswith('_sheet_'): r.pop(key)
    for key in ('submit_hash', 'operation_id', 'submit_owner', 'legacy_values', '_sheet_row', '_sheet_hash', '_sheet_revision'):
        r.pop(key, None)
    b = r['before']
    # Preserve the recorded grade, even when today's institution policy differs.
    r['current_risk'] = {key:b[key] for key in ('p','s','score','grade')}
    for target in [r, r.get('after') or {}]:
        target.pop('photo_view_url', None)
        fid = target.get('photo_id')
        target['photo_url'] = cfg.public_path(f"/api/assessments/{r['id']}/photos/{fid}") if fid else ''
    r['reassessment_policy'] = None
    try:
        r['reassessment_policy'] = record_policy(r, org).model_dump()
    except ValueError:
        pass
    if not org.department_enabled:
        r.pop('department', None)
    if org.submitter_name.mode == 'disabled':
        r.pop('submitter_name', None)
    else:
        r['submitter_name'] = display_name(r.get('submitter_name'))
    for target in [r['before'], r.get('after') or {}]:
        if 'tone' not in target:
            target['tone'] = next((g.tone for g in org.policy.grades if g.name == target.get('grade')), -1)
            target['urgent'] = next((g.urgent for g in org.policy.grades if g.name == target.get('grade')), False)
    return r

