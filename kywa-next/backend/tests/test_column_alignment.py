import copy
import io
import uuid
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from backend.column_alignment import center_requests,centered_template,SHORT_CANONICAL
from backend.excel_kywa import create_excel
from backend.organization import load_organization
from backend.sheet_schema import LABELS,base_keys
from backend.visible_layout import VISIBLE_KEYS,VisibleLayout
from backend.sheet_sync import Store,CONFIG
from backend.tests.test_institutions import current_record
from backend.tests.test_sheet_sync import Rows

ORGS=('kywa','ayf','fowi','khidi','knps','knf','kohi','cayf')


def layout(org):
    keys=base_keys(org)
    keys += [k for k in VISIBLE_KEYS if k not in keys]+['before_photo2']
    if not org.department_enabled:keys.remove('department')
    if org.submitter_name.mode=='disabled':keys.remove('submitter_name')
    return VisibleLayout([LABELS[k] for k in keys],org)


@pytest.mark.parametrize('identity',ORGS)
def test_existing_column_alignment_respects_name_and_facility_only_layouts(identity):
    current=layout(load_organization(identity));requests=center_requests(current,7)
    columns={r['repeatCell']['range']['startColumnIndex'] for r in requests}
    assert {0,1}.issubset(columns)
    if identity=='khidi':assert 3 in columns and 4 not in columns and 5 in columns
    elif identity=='ayf':assert 2 not in columns and 3 in columns and 5 in columns
    else:assert 2 in columns and 3 not in columns and 4 in columns and 6 in columns
    for request in requests:
        repeat=request['repeatCell']
        assert repeat['fields']=='userEnteredFormat.horizontalAlignment'
        assert repeat['range']['startRowIndex']==1 and 'endRowIndex' not in repeat['range']
        assert repeat['cell']=={'userEnteredFormat':{'horizontalAlignment':'CENTER'}}


def test_new_append_after_all_rows_deleted_centers_values_without_losing_fonts_or_links():
    org=load_organization('kywa')
    class Capture(Rows):
        def save(self,changes,events=(),extra=()):
            for item in extra:
                if 'appendCells' in item:self.last_cells=copy.deepcopy(item['appendCells']['rows'][0]['values'])
            return super().save(changes,events,extra)
    g=Capture();store=Store(SimpleNamespace(settings=SimpleNamespace(organization=org)),g)
    record=current_record(org);record.update(operation_id=str(uuid.uuid4()),submit_hash='a',submit_owner='b')
    record['photo_id']='photo';record['photo_view_url']='https://drive.google.com/file/d/photo/view?usp=drivesdk'
    store.append([record])
    for index,cell in enumerate(g.last_cells):
        fmt=cell['userEnteredFormat']
        assert fmt['horizontalAlignment']==('CENTER' if index in SHORT_CANONICAL else 'LEFT')
        assert fmt['textFormat']['fontFamily']=='Roboto'
    assert g.last_cells[12]['userEnteredFormat']['textFormat']['link']['uri']==record['photo_view_url']


def test_hidden_format_template_change_preserves_every_other_format_and_input():
    original=[{'horizontalAlignment':'LEFT','textFormat':{'fontFamily':'Roboto','fontSize':10},
        'numberFormat':{'type':'NUMBER','pattern':'0'},'wrapStrategy':'WRAP','borders':{'bottom':{'style':'SOLID'}}} for _ in range(19)]
    result=centered_template(original)
    assert all(f['horizontalAlignment']=='LEFT' for f in original)
    for index in range(19):
        expected=copy.deepcopy(original[index])
        if index in SHORT_CANONICAL:expected['horizontalAlignment']='CENTER'
        assert result[index]==expected


@pytest.mark.parametrize('identity',['kywa','khidi','ayf'])
def test_table_expansion_cannot_replace_the_new_rows_short_alignment(identity):
    from backend.sheet_sync import GoogleRows
    g=GoogleRows.__new__(GoogleRows);g.sheet_id=7;g.sid='copy';g.api=None
    g.layout=layout(load_organization(identity))
    g.repo=SimpleNamespace(settings=SimpleNamespace(sheet_name='평가'))
    g._sheet_info={'properties':{'sheetId':7},'tables':[{'tableId':'table','range':{'sheetId':7,'startRowIndex':0,'endRowIndex':2,'endColumnIndex':len(g.layout.header)}}]}
    styles=[{'horizontalAlignment':'CENTER','textFormat':{'fontFamily':'Roboto','fontSize':10}} for _ in g.layout.header]
    def batch(requests):
        for request in requests:
            if 'updateTable' in request:
                # Observed real Sheets behavior when a native table grows.
                for style in styles:style.pop('horizontalAlignment',None)
            elif request.get('updateCells',{}).get('fields')=='userEnteredFormat.horizontalAlignment':
                for index,cell in enumerate(request['updateCells']['rows'][0]['values']):
                    styles[index]['horizontalAlignment']=cell['userEnteredFormat']['horizontalAlignment']
    g.batch=batch
    g.finish_append([[],[],[]],[2])
    assert styles[0]['horizontalAlignment']=='CENTER'
    for canonical,physical in enumerate(g.layout.positions):
        if physical is not None:
            assert styles[physical]['horizontalAlignment']==('CENTER' if canonical in SHORT_CANONICAL else 'LEFT')
            assert styles[physical]['textFormat']=={'fontFamily':'Roboto','fontSize':10}


@pytest.mark.parametrize('identity',ORGS)
def test_export_short_columns_are_centered_but_narratives_and_law_text_remain_left(identity):
    org=load_organization(identity);record=current_record(org)
    record['before']['law']='산업안전보건법 제38조'
    wb=load_workbook(io.BytesIO(create_excel([record],SimpleNamespace(get=lambda _:None),org)))
    ws=wb['위험성평가'];by_header={cell.value:cell.column for cell in ws[1]}
    for label in ('시설명','담당 부서','유해위험요인','빈도','강도','점수','위험등급',
                  '개선후 빈도','개선후 강도','개선후 점수','개선후 위험등급','조치일자','처리상태','제출자 성명'):
        if label in by_header:assert ws.cell(2,by_header[label]).alignment.horizontal=='center',label
    for label in ('장소','위험상황','감소대책','관련근거','개선조치 내용'):
        assert ws.cell(2,by_header[label]).alignment.horizontal=='left',label
    laws=wb['관련근거']
    for col in (1,4,5):assert laws.cell(2,col).alignment.horizontal=='center'
    assert laws.cell(2,3).hyperlink and ws.page_setup.orientation=='landscape'

    assert wb['집계']['B2'].alignment.horizontal=='center'
    criteria=wb['평가기준']
    for row in criteria.iter_rows(min_row=2):
        for cell in row:
            if cell.column!=4 or isinstance(cell.value,(int,float)):
                assert cell.alignment.horizontal=='center'
            else:assert cell.alignment.horizontal=='left'
