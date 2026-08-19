import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ==========================================
# 1. 한글 폰트 등록 (환경에 맞는 TTF 경로 지정)
# ==========================================
# Windows: 'malgun.ttf', Mac: 'AppleGothic.ttf' 또는 NanumGothic.ttf
FONT_NAME = 'MalgunGothic'
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, 'malgun.ttf'))
except Exception:
    # 폰트 로드 실패 시 디폴트 시스템 폰트 대체 경로 지정 가능
    FONT_NAME = 'Helvetica'


# ==========================================
# 2. 페이지 번호 및 머리말/꼬리말 Canvas 클래스
# ==========================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont(FONT_NAME, 8)
        self.setFillColor(colors.HexColor('#666666'))
        
        # [머리말]
        self.drawString(15 * mm, 285 * mm, "2026년 본원 위험성평가 결과 보고서")
        self.setStrokeColor(colors.HexColor('#CCCCCC'))
        self.setLineWidth(0.5)
        self.line(15 * mm, 282 * mm, 195 * mm, 282 * mm)

        # [꼬리말]
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(195 * mm, 10 * mm, page_str)
        self.drawString(15 * mm, 10 * mm, "한국청소년활동진흥원 (KYWA)")
        self.line(15 * mm, 14 * mm, 195 * mm, 14 * mm)
        
        self.restoreState()


# ==========================================
# 3. PDF 생성 메인 함수
# ==========================================
def generate_risk_assessment_report(output_filename):
    # 문서 설정 (A4, 여백 설정)
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm
    )

    story = []
    
    # 스타일 정의
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor('#1A365D'),
        alignment=1, # Center
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True # Page break 방지
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#2D3748')
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1 # Center
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#2D3748')
    )

    # ----------------------------------------------------
    # 문서 제목 및 개요
    # ----------------------------------------------------
    story.append(Paragraph("<b>본원 사업장 위험성평가 결과 분석 및 개선대책</b>", title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1A365D'), spaceAfter=10))

    story.append(Paragraph("<b>1. 추진 배경 및 평가 개요</b>", h1_style))
    intro_text = """
    • <b>추진 배경:</b> 「산업안전보건법」 및 안전보건관리체계 구축 지침에 따른 원내 유해·위험요인 선제적 발굴 및 제거<br/>
    • <b>평가 대상:</b> 본원 내 전 부서 사무 공간, 통행로, 시설 및 전기 설비 등 (총 55건 발굴)<br/>
    • <b>평가 결과:</b> 위험등급 [높음] 2건, [보통/낮음/매우낮음] 53건 (개선대책 수립률 100%)
    """
    story.append(Paragraph(intro_text, body_style))
    story.append(Spacer(1, 10))

    # ----------------------------------------------------
    # 세부 현황 및 위험성평가 테이블 데이터 구성
    # ----------------------------------------------------
    story.append(Paragraph("<b>2. 세부 위험성평가 및 개선조치 현황</b>", h1_style))

    # 샘플 데이터셋 (파싱 데이터 연결 부분)
    raw_data = [
        {
            "date": "2026-04-16", "dept": "안전경영부", "location": "사무실", "cat": "작업 특성",
            "risk": "장시간 부적절한 자세로 컴퓨터 작업 수행에 따른 근골격계 질환 위험",
            "score": "3/1/3 (매우낮음)", "plan": "모니터 높이 조절, 정기 스트레칭 및 인체공학 집기 보급",
            "img_before": "photo_placeholder.png", "img_after": "photo_placeholder.png"
        },
        {
            "date": "2026-04-17", "dept": "안전경영부", "location": "사무실 책상하부", "cat": "전기적 요인",
            "risk": "책상 하부 멀티탭 및 전선 노출로 인한 보행자 전도 및 감전/화재 위험",
            "score": "3/2/6 (낮음)", "plan": "케이블 타이를 활용한 배선 정리 및 몰딩 설치, 멀티탭 책상 고정",
            "img_before": None, "img_after": None
        },
        {
            "date": "2026-05-22", "dept": "활동인증부", "location": "출장 이동 경로", "cat": "작업 특성",
            "risk": "장거리 및 다수의 출장으로 인한 운전 피로 누적 및 차량 사고 위험",
            "score": "3/3/9 (높음)", "plan": "대중교통 이용 활성화, 2시간 운전 후 15분 휴식 의무화",
            "img_before": None, "img_after": None
        }
    ]

    # 테이블 헤더 정의
    table_data = [[
        Paragraph("<b>일자/부서</b>", table_header_style),
        Paragraph("<b>위험요인 및 장소</b>", table_header_style),
        Paragraph("<b>위험성<br/>(빈도/강도/점수)</b>", table_header_style),
        Paragraph("<b>개선대책 및 관련근거</b>", table_header_style),
        Paragraph("<b>개선전 사진</b>", table_header_style),
        Paragraph("<b>개선후 사진</b>", table_header_style)
    ]]

    # 헬퍼 함수: 이미지 안전 로드 (누락 및 경로 오류 처리)
    def get_image_flowable(img_path):
        if img_path and os.path.exists(img_path):
            try:
                return Image(img_path, width=28 * mm, height=21 * mm)
            except Exception:
                pass
        # 이미지 없거나 로드 실패 시 대체 텍스트 표시
        return Paragraph("<font color='#A0AEC0'>[사진 없음]</font>", table_cell_style)

    # 데이터 행 추가 및 자동 줄바꿈(Paragraph) 감싸기
    for item in raw_data:
        col_info = Paragraph(f"<b>{item['date']}</b><br/>{item['dept']}<br/>({item['location']})", table_cell_style)
        col_risk = Paragraph(f"<b>[{item['cat']}]</b><br/>{item['risk']}", table_cell_style)
        col_score = Paragraph(f"{item['score']}", table_cell_style)
        col_plan = Paragraph(f"{item['plan']}", table_cell_style)
        
        img_b = get_image_flowable(item['img_before'])
        img_a = get_image_flowable(item['img_after'])

        table_data.append([col_info, col_risk, col_score, col_plan, img_b, img_a])

    # 너비 계산 (A4 가로 폭 180mm 기준 분배)
    col_widths = [30 * mm, 45 * mm, 25 * mm, 44 * mm, 18 * mm, 18 * mm]
    
    report_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    report_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')])
    ]))

    story.append(report_table)

    # 문서 빌드 실행
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    generate_risk_assessment_report("KYWA_위험성평가_개선보고서_보완본.pdf")
