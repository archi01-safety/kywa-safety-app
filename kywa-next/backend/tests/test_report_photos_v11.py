import io
import zipfile
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfReader
from openpyxl import load_workbook
from backend.config import Settings
from backend.excel_kywa import create_excel
from backend.report_semantic import Photos,hwpx
from backend.report_model import compose
from backend.report_layout import build,pdf
from backend.services import AIService
from backend.visible_layout import VisibleLayout
from backend.migrate_photos import plan
from backend.sheet_schema import SheetSchemaError
from backend.compact_storage import VISIBLE
from backend.tests.test_institutions import current_record

NS={'p':'http://www.hancom.co.kr/hwpml/2011/paragraph'}


@pytest.mark.parametrize('org_id',['kywa','fowi','knps','knf','kohi','khidi','cayf','ayf'])
def test_new_rightmost_column_preserves_institution_mapping(org_id):
    cfg=Settings(_env_file=None,organization_id=org_id);org=cfg.organization
    header=VISIBLE.copy()
    if org_id=='ayf':header=[h for i,h in enumerate(header) if i not in (2,18)]
    if org_id=='khidi':header.insert(3,header.pop(18));header[3]='이름'
    target=plan(header,org,{})
    assert target[:-1]==header and target[-1]=='개선 전 사진 2'
    row=list(range(20));adapter=VisibleLayout(target,org)
    canonical=adapter.canonical(adapter.physical(row))
    assert canonical==[v if i not in (2,18) or org_id!='ayf' else '' for i,v in enumerate(row)]
    assert len(target)==(18 if org_id=='ayf' else 20)
    assert plan(target,org,{})==target
    with pytest.raises(SheetSchemaError):plan(header,org,{('request','pending'):(1,{'state':'appending'})})


def records(cfg,count):
    result=[]
    for i in range(count):
        record=current_record(cfg.organization);record['before'].update(scenario='바닥 케이블로 인한 걸림 위험',solution='배선 정리 및 고정',law='산업안전보건기준에 관한 규칙 제3조(전도의 방지)')
        record.update(photo_id=f'before-{i}',photo_ids=[f'before-{i}',f'before2-{i}'])
        record['after']={'p':1,'s':1,'score':1,'grade':'매우 낮음','text':'케이블 정리 및 고정','photo_id':f'after-{i}','created_at':'2026-11-13T09:00:00+09:00'}
        record['status']='완료';result.append(record)
    return result


def store():
    data=io.BytesIO();Image.new('RGB',(600,400),'#306485').save(data,'JPEG')
    return SimpleNamespace(get=lambda key:data.getvalue())


@pytest.mark.parametrize('count',[1,2,3,16])
def test_pdf_hwpx_have_three_picture_columns_and_real_links(count):
    cfg=Settings(_env_file=None);data=records(cfg,count);photos=Photos(data,store());model=compose(data,AIService(cfg))
    assert all(len(keys)==3 for keys in photos.keys)
    pages=build(model,data,photos)
    document=PdfReader(io.BytesIO(pdf(pages)))
    assert len(document.pages)==1+(count+1)//2
    links=[a.get_object() for p in document.pages for a in p.get('/Annots',[]) if a.get_object().get('/A')]
    assert len(links)==count and all(str(a['/A']['/URI']).startswith('https://www.law.go.kr/') for a in links)
    result=hwpx(model,photos);z=zipfile.ZipFile(io.BytesIO(result));root=ET.fromstring(z.read('Contents/section0.xml'))
    pictures=[table for table in root.findall('.//p:tbl',NS) if table.get('colCnt')=='3' and table.get('rowCnt')=='2' and table.findall('.//p:pic',NS)]
    assert len(pictures)==count
    assert len(root.findall('.//p:fieldBegin',NS))==count
    assert all(t.get('colCnt')!='1' or t.get('rowCnt')!='1' for t in root.findall('.//p:tbl',NS))


def test_excel_second_photo_and_all_hyperlinks_and_no_internal_values():
    cfg=Settings(_env_file=None);data=records(cfg,1);data[0]['before']['_internal_risk']={'score':300,'facts':'private'}
    wb=load_workbook(io.BytesIO(create_excel(data,store(),cfg.organization)))
    ws=wb['위험성평가'];headers=[c.value for c in ws[1]]
    assert headers[11:13]==['사진 기록','개선 전 사진 2'] and len(ws._images)==3
    assert ws.cell(2,11).hyperlink and wb['관련근거'].cell(2,3).hyperlink
    assert all('_internal_risk' not in str(cell.value) and cell.value!='private' for sheet in wb for row in sheet for cell in row)
    assert {i.anchor._from.col for i in ws._images}=={11,12,17}
