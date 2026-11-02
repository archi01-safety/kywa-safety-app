import copy
import uuid
from types import SimpleNamespace
import pytest
from backend.organization import load_organization
from backend.visible_layout import VisibleLayout, VISIBLE_KEYS
from backend.sheet_schema import LABELS, base_keys
from backend.compact_storage import visible
from backend.tests.test_institutions import current_record
from backend.tests.test_sheet_sync import Rows
from backend.sheet_sync import Store
from backend.prompts import institution_prompt
from backend.report_model import aggregate
from backend.filenames import report_filename

PARTNERS = ['ayf','fowi','khidi','knps','knf','kohi','cayf']


@pytest.mark.parametrize('identity',PARTNERS)
def test_partner_export_names_grades_and_editable_structure(identity):
    import io, zipfile
    from pypdf import PdfReader
    from openpyxl import load_workbook
    from backend.tests.test_institutions import settings
    from backend.services import AIService
    from backend.report_model import compose
    from backend.report_layout import build, pdf
    from backend.report_semantic import Photos, hwpx
    from backend.reports import excel
    cfg=settings(identity);org=cfg.organization
    records=[current_record(org) for _ in range(2)]
    records[1]['facility']=org.facilities[-1]
    model=compose(records,AIService(cfg),org=org)
    assert org.name in model['facts']['title'] or len(org.facilities)==1
    photos=Photos(records,None)
    reader=PdfReader(io.BytesIO(pdf(build(model,records,photos))))
    assert len(reader.pages)==2
    text=''.join(p.extract_text() for p in reader.pages)
    assert '홍㉠㉢' not in text and '한국청소년활동진흥원 통합' not in text
    z=zipfile.ZipFile(io.BytesIO(hwpx(model,photos)))
    xml=z.read('Contents/section0.xml').decode()
    assert xml.count('pageBreak="1"')==1 and '<hp:drawText' not in xml
    assert org.name in xml or len(org.facilities)==1
    if '약간 높음' not in model['facts']['grade_order']: assert '약간 높음' not in xml
    book=load_workbook(io.BytesIO(excel(records,photos,org)))
    sheet=book['위험성평가']
    assert sheet.page_setup.orientation=='landscape' and sheet.page_setup.paperSize==int(sheet.PAPERSIZE_A3)


@pytest.mark.parametrize('identity',PARTNERS)
def test_partner_columns_prompt_policy_and_reports(identity):
    org=load_organization(identity)
    keys=base_keys(org)+[k for k in VISIBLE_KEYS if k not in base_keys(org)]
    header=[LABELS[k] for k in keys]
    if identity=='khidi': header[3]='이름'
    adapter=VisibleLayout(header,org)
    r=current_record(org);raw=adapter.physical(visible(r))
    assert adapter.canonical(raw)==visible(r)
    assert raw[3 if identity=='khidi' else 18]==r['submitter_name']
    text=institution_prompt(org,org.facilities[0],org.departments[0],'시험용 경미한 바닥 파손')
    assert org.name in text and '한국청소년활동진흥원의 안전관리 전문가' not in text
    assert '안전수칙 및 작업표준은 있음을 전제로' in text
    assert '최대 '+str({'fowi':4,'khidi':5}.get(identity,6))+'점' in text
    assert str(org.policy.risk(5,3)['grade']) in text
    assert 'score, grade' not in text
    other=copy.deepcopy(r);other['facility']=org.facilities[-1]
    facts=aggregate([r,other],org)
    if r['facility'] != other['facility']: assert org.name+' 통합' in facts['title']
    assert facts['grade_order']==[g.name for g in reversed(org.policy.grades)]
    assert report_filename('', 'pdf','2026-11-02T15:02:00+00:00',org.short_name)==org.short_name+'_위험성평가_20261103.pdf'


@pytest.mark.parametrize('identity',PARTNERS)
def test_partner_delete_edit_and_streamlit_adoption(identity):
    org=load_organization(identity);g=Rows();store=Store(SimpleNamespace(settings=SimpleNamespace(organization=org)),g)
    def fresh():
        r=current_record(org);r.update(operation_id=str(uuid.uuid4()),submit_hash='test',submit_owner='test');return r
    r=fresh();store.append([r]);assert store.recover_append(r['operation_id'])[0]['id']==r['id']
    current,_=store.sync();g.patch(current[0]['_sheet_metadata_id'],{6:5,7:3,8:999})
    current,issues=store.sync();assert not issues
    assert current[0]['before']['score']==15 and current[0]['before']['grade']==org.policy.risk(5,3)['grade']
    g.delete(1);second=fresh();store.append([second])
    current,issues=store.sync();assert [x['id'] for x in current]==[second['id']] and not issues
    assert store.recover_append(r['operation_id'])[0]['_sheet_deleted']
    g.rows.append(visible(second).copy());current,issues=store.sync()
    adopted=next(x for x in current if x['id']!=second['id'])
    assert adopted['organization_id']==org.id and len(current)==2
