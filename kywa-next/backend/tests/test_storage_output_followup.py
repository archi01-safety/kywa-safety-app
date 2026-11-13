import copy
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from types import SimpleNamespace
import pytest
from openpyxl import load_workbook
from PIL import Image
from backend.tests.test_institutions import settings, current_record
from backend.report_model import compose, Narrative, Detail, Audit
from backend.report_semantic import Photos, hwpx, ReportError
from backend.services import AIService
from backend.excel_kywa import create_excel
from backend.sheet_format import canonical, fingerprint


def test_date_fingerprint_ignores_google_display_and_integer_representation():
    raw=['2026-10-30T15:53:41+09:00']+['']*18
    displayed=raw.copy();displayed[0]='2026. 10. 30 오후 3:53:41'
    numeric=canonical(raw);numeric[6]='1.0';raw[6]=1;displayed[6]=1.0
    assert fingerprint(raw)==fingerprint(displayed)==fingerprint(numeric)
    assert canonical(raw)[0]==pytest.approx(46325.662280093)


def test_excel_print_dates_masking_integers_and_picture_anchors():
    cfg=settings('kywa');r=current_record(cfg.organization)
    r['submitter_name']='홍길동';r['photo_id']='before'
    r['after']={'p':'1.0','s':4.0,'score':'4.0','grade':'낮음','text':'정비 완료','photo_id':'after',
                'created_at':'2026-10-29T16:30:00+00:00','actor':'pin-admin'}
    image=io.BytesIO();Image.new('RGB',(400,900),'green').save(image,'JPEG')
    wb=load_workbook(io.BytesIO(create_excel([r],SimpleNamespace(get=lambda _:image.getvalue()),cfg.organization)))
    ws=wb['위험성평가'];headers=[c.value for c in ws[1]]
    assert not set(headers)&{'타임스탬프','평가기준','평가ID','재평가 기준','처리자','조치시각'}
    assert ws['V2'].value=='홍㉠㉢' and ws['T2'].value.date()==date(2026,10,30)
    assert [ws.cell(2,c).value for c in (14,15,16)]==[1,4,4]
    assert all(ws.cell(2,c).number_format=='0' and ws.cell(2,c).data_type=='n' for c in (6,7,8,14,15,16))
    assert ws.page_setup.orientation=='landscape' and str(ws.page_setup.paperSize)==ws.PAPERSIZE_A3
    assert (ws.page_setup.fitToWidth,ws.page_setup.fitToHeight)==(1,0)
    assert ws.sheet_view.view=='pageBreakPreview' and ws.print_title_rows=='$1:$1'
    assert [s.title for s in wb if s.sheet_view.tabSelected]==['위험성평가']
    assert wb.active==ws and ws.page_margins.left==.7
    assert len(ws._images)==2
    for image in ws._images:
        assert image.anchor.editAs=='twoCell'
        assert image.anchor._from.row==image.anchor.to.row==1
        assert image.anchor._from.col in (11,17) and image.anchor.to.col==image.anchor._from.col
        assert image.anchor.to.rowOff < ws.row_dimensions[2].height*96/72*9525
    r['after']['score']=4.5
    with pytest.raises(ValueError):create_excel([r],None,cfg.organization)


@pytest.mark.parametrize('count',[1,2,3,16,30])
def test_semantic_hwpx_whole_paragraphs_and_real_tables(count):
    cfg=settings('kywa');records=[current_record(cfg.organization) for _ in range(count)]
    model=compose(records,AIService(cfg));result=hwpx(model,Photos(records,None))
    z=zipfile.ZipFile(io.BytesIO(result));assert z.testzip() is None
    assert {'version.xml','settings.xml','META-INF/container.xml','Contents/content.hpf'}<=set(z.namelist())
    root=ET.fromstring(z.read('Contents/section0.xml'));ns={'p':'http://www.hancom.co.kr/hwpml/2011/paragraph'}
    assert not root.findall('.//p:drawText',ns)
    assert len([p for p in root.findall('p:p',ns) if p.get('pageBreak')=='1'])==(count+1)//2
    assert all(t.get('rowCnt')!='1' or t.get('colCnt')!='1' for t in root.findall('.//p:tbl',ns))
    assert model['overview'] in [t.text for t in root.findall('.//p:t',ns)]


def test_summary_repair_once_and_rejects_repeated_grounding_failure():
    cfg=settings('kywa');r=current_record(cfg.organization)
    narrative=Narrative(overview='단차로 인한 넘어짐 위험의 개선이 필요함.',priorities=['보행 구간 단차를 보수하여야 함.'],
        details=[Detail(number=1,scenario='단차',solution='보수',action='',law='확인')])
    class AI:
        settings=SimpleNamespace(demo=False)
        def __init__(self,valid):self.calls=0;self.valid=valid
        def _generate(self,prompt,schema):
            self.calls+=1
            return narrative if schema==Narrative else Audit(valid=self.calls>=4 and self.valid,reason='검증')
    ai=AI(True);assert compose([r],ai)['facts']['total']==1 and ai.calls==4
    ai=AI(False)
    with pytest.raises(ReportError) as exc:compose([r],ai)
    assert exc.value.code=='grounding' and ai.calls==4


def test_unavailable_report_provider_is_not_reported_as_grounding_failure():
    cfg=settings('kywa')
    class AI:
        settings=SimpleNamespace(demo=False)
        def _generate(self,*args):raise TimeoutError('private details')
    with pytest.raises(ReportError) as exc:compose([current_record(cfg.organization)],AI())
    assert exc.value.code=='communication' and 'private' not in str(exc.value)
