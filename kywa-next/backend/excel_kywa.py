"""KYWA print-ready detail workbook; operational identities stay server-side."""
import io
import math
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.page import PageMargins
from openpyxl.drawing.image import Image
from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor, AnchorMarker
from openpyxl.utils import get_column_letter
from openpyxl.utils.units import pixels_to_EMU
from .domain import HEADERS, sheet_row
from .submitter_name import display_name

WIDTHS=[12,18,18,16,38,5,5,6,10,38,26,24,5,5,6,10,24,38,12,10,12]


def number(value):
    if value in ('',None): return None
    n=float(value)
    if not math.isfinite(n) or not n.is_integer(): raise ValueError('평가 점수가 정수가 아닙니다.')
    return int(n)


def create_excel(records,store,org):
    from .reports import safe_photo, policy_snapshots
    wb=Workbook(); ws=wb.active; ws.title='위험성평가'
    headers=HEADERS[1:18]+['개선조치 내용','조치일자','처리상태','제출자 성명']
    ws.append(headers)
    for cell in ws[1]:
        cell.font=Font(name='맑은 고딕',size=10,color='FFFFFF',bold=True)
        cell.fill=PatternFill('solid',fgColor='123A63')
        cell.alignment=Alignment(wrap_text=True,vertical='center',horizontal='center')
    ws.row_dimensions[1].height=34
    for col,width in enumerate(WIDTHS,1): ws.column_dimensions[get_column_letter(col)].width=width
    for idx,r in enumerate(records,2):
        after=r.get('after') or {}
        day=None
        if after.get('created_at'):
            from .migrate import timestamp
            day=datetime.fromisoformat(timestamp(after['created_at'])).astimezone(ZoneInfo('Asia/Seoul')).date()
        values=sheet_row(r)[1:18]+[after.get('text',''),day,r['status'],display_name(r.get('submitter_name'))]
        for c in (5,6,7,12,13,14): values[c]=number(values[c])
        height=100
        for col,value in enumerate(values,1):
            if col in (12,17): value=''
            if isinstance(value,str) and value.startswith(('=','+','-','@')): value="'"+value
            cell=ws.cell(idx,col,value)
            cell.font=Font(name='맑은 고딕',size=10)
            cell.alignment=Alignment(wrap_text=True,vertical='center',horizontal='center' if col in (6,7,8,9,13,14,15,16,19,20,21) else 'left')
            if col in (6,7,8,13,14,15): cell.number_format='0'
            if col==19: cell.number_format='yyyy. mm. dd'
            if idx%2==0: cell.fill=PatternFill('solid',fgColor='F1F5FA')
            if isinstance(value,str):
                lines=sum(max(1,math.ceil(sum(2 if ord(ch)>127 else 1 for ch in line)/max(4,WIDTHS[col-1]-2))) for line in value.split('\n'))
                height=max(height,min(409,lines*13+12))
        ws.row_dimensions[idx].height=height
        for col,fid in [(12,r.get('photo_id')),(17,after.get('photo_id'))]:
            data=safe_photo(store,fid)
            if not data:
                ws.cell(idx,col,'사진 불러오기 실패' if fid else '사진 없음'); continue
            pic=Image(io.BytesIO(data)); w,h=WIDTHS[col-1]*7+5,height*96/72
            ratio=min((w-12)/pic.width,(h-12)/pic.height)
            pic.width,pic.height=pic.width*ratio,pic.height*ratio
            x,y=(w-pic.width)/2,(h-pic.height)/2
            pic.anchor=TwoCellAnchor(editAs='twoCell',
                _from=AnchorMarker(col=col-1,row=idx-1,colOff=pixels_to_EMU(x),rowOff=pixels_to_EMU(y)),
                to=AnchorMarker(col=col-1,row=idx-1,colOff=pixels_to_EMU(x+pic.width),rowOff=pixels_to_EMU(y+pic.height)))
            ws.add_image(pic)
    ws.freeze_panes='F2';ws.auto_filter.ref=ws.dimensions
    ws.sheet_view.view='pageBreakPreview';ws.sheet_view.tabSelected=True
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
    ws.page_margins=PageMargins(left=.7,right=.7,top=.75,bottom=.75,header=.3,footer=.3)
    ws.print_area=f'A1:U{ws.max_row}';ws.print_title_rows='1:1'
    ws.oddFooter.center.text='&P / &N'
    summary=wb.create_sheet('집계')
    for row in [('기관',org.name),('전체 건수',len(records)),('완료 건수',sum(r['status']=='완료' for r in records)),('미완료 건수',sum(r['status']!='완료' for r in records)),*Counter(r['before']['grade'] for r in records).items()]: summary.append(row)
    summary.column_dimensions['A'].width=25;summary.column_dimensions['B'].width=60
    policies=policy_snapshots(records)
    if policies:
        criteria=wb.create_sheet('평가기준');criteria.append(['버전','구분','빈도','강도 / 설명','점수','등급'])
        for policy in policies:
            for key,title in [('p_levels','빈도'),('s_levels','강도')]:
                for level in policy[key]: criteria.append([policy['version'],title,level['value'],level['description']])
            for c in policy['cells']: criteria.append([policy['version'],policy['method'],c['p'],c['s'],c['score'],c['grade']])
    for sheet in wb:
        if sheet!=ws: sheet.sheet_view.tabSelected=False
        for row in sheet:
            for cell in row:
                if cell.data_type=='f': cell.value="'"+cell.value
    wb.active=0
    out=io.BytesIO();wb.save(out);return out.getvalue()
