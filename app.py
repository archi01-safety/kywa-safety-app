import os
import ssl
import json
import requests
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from docx import Document

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# 2.5 로고 이미지 로드
logo_path = "kywa_logo.png"
logo_img = None
if os.path.exists(logo_path):
    logo_img = Image.open(logo_path)

# 3. 헤더 디자인 (수정본)
header_col1, header_col2 = st.columns([1, 4])
with header_col1:
    if logo_img:
        # 로고 이미지 표시 (너비는 적절히 조절하세요)
        st.image(logo_img, width=300) 
    else:
        # 이미지가 없을 경우 기존 텍스트 표시
        st.markdown("<h2 style='color: #E60012; margin-top: 0;'>KYWA</h2>", unsafe_allow_html=True)

with header_col2:
    st.title("🚨 KYWA AI 위험성평가 시스템")
    st.caption("Korea Youth Work Agency - 스마트 안전관리 플랫폼")

# 4. 커스텀 CSS (표 너비 최적화 반영)
st.markdown("""
    <style>
    .stButton>button { 
        width: 100% !important; border-radius: 8px; font-weight: bold; 
        background-color: #E60012; color: white; height: 3.5em; border: none; 
        transition: all 0.3s ease;
    }
    .stButton>button:hover { background-color: #C1000F !important; color: white !important; }
    
    .report-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.95em; table-layout: fixed; }
    .report-table th, .report-table td { padding: 12px; border: 1px solid #dee2e6; vertical-align: top; word-break: keep-all; line-height: 1.6; }
    .report-table th { background-color: #f1f3f5; text-align: center; font-weight: bold; }
    
    /* 화면 표시용 열 너비 설정 */
    .report-table th:nth-child(1) { width: 8%; }  /* 분류 */
    .report-table th:nth-child(2) { width: 18%; } /* 위험상황 */
    .report-table th:nth-child(3) { width: 6%; }  /* 빈도 */
    .report-table th:nth-child(4) { width: 6%; }  /* 강도 */
    .report-table th:nth-child(5) { width: 6%; }  /* 점수 */
    .report-table th:nth-child(6) { width: 8%; }  /* 등급 */
    .report-table th:nth-child(7) { width: 20%; } /* 관련근거 */
    .report-table th:nth-child(8) { width: 28%; } /* 감소대책 */
    
    .grade-high { background-color: #ffe3e3 !important; color: #b91c1c !important; font-weight: bold; text-align: center; }
    .grade-medium { background-color: #fff5dc !important; color: #92400e !important; font-weight: bold; text-align: center; }
    .grade-low { background-color: #ebfbee !important; color: #166534 !important; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

GRADE_MAP = {'high': '높음', 'medium': '보통', 'low': '낮음', 'High': '높음', 'Medium': '보통', 'Low': '낮음', '매우 높음': '높음', '약간 높음': '보통'}

# --- 엑셀 파일 생성 함수 (열 너비 최적화 포함) ---
def create_excel(data):
    if not data: return None
    df = pd.DataFrame(data)
    column_mapping = {
        'category': '분류', 'scenario': '위험상황', 'p': '빈도', 's': '강도', 
        'score': '점수', 'grade': '등급', 'law': '관련근거', 'solution': '감소대책'
    }
    df = df.rename(columns=column_mapping)
    final_cols = ['분류', '위험상황', '빈도', '강도', '점수', '등급', '관련근거', '감소대책']
    df = df[[c for c in final_cols if c in df.columns]]
    
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='위험성평가_결과')
        
        workbook  = writer.book
        worksheet = writer.sheets['위험성평가_결과']
        
        # 1. 포맷 정의
        # 텍스트가 많은 컬럼용 (양쪽 정렬 + 상단 정렬)
        wrap_format = workbook.add_format()
        wrap_format.set_text_wrap()
        wrap_format.set_align('top')

        # 짧은 텍스트 컬럼용 (가운데 정렬 + 상단 정렬)
        center_top_format = workbook.add_format()
        center_top_format.set_align('center') # 가로 가운데
        center_top_format.set_align('top')    # 세로 상단

        # 2. 열 너비 및 포맷 적용
        worksheet.set_column(0, 0, 12, center_top_format)    # 분류 (가운데/상단)
        worksheet.set_column(1, 1, 25, wrap_format)          # 위험상황 (양쪽/상단)
        worksheet.set_column(2, 4, 6, center_top_format)     # 빈도, 강도, 점수 (가운데/상단)
        worksheet.set_column(5, 5, 10, center_top_format)    # 등급 (가운데/상단)
        worksheet.set_column(6, 6, 30, wrap_format)          # 관련근거 (양쪽/상단)
        worksheet.set_column(7, 7, 40, wrap_format)          # 감소대책 (양쪽/상단)
        
    return bio.getvalue()

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL # 이름을 이걸로 변경

def create_docx(data):
    if not data: return None
    doc = Document()
    doc.add_heading('KYWA AI 위험성평가 결과 보고서', 0)
    
    table = doc.add_table(rows=1, cols=8)
    table.style = 'Table Grid'
    
    headers = ['분류', '위험상황', '빈도', '강도', '점수', '등급', '근거', '대책']
    hdr_cells = table.rows[0].cells
    for i, txt in enumerate(headers):
        hdr_cells[i].text = txt
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for item in data:
        row_cells = table.add_row().cells
        keys = ['category', 'scenario', 'p', 's', 'score', 'grade', 'law', 'solution']
        center_cols = [0, 2, 3, 4, 5]

        for idx, key in enumerate(keys):
            cell = row_cells[idx]
            cell.text = str(item.get(key, ''))
            
            # 수직 정렬 코드를 아래와 같이 수정 (WD_ALIGN_VERTICAL 사용)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP 
            
            if idx in center_cols:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# 5. 사이드바 및 모델 설정
with st.sidebar:
    api_key = st.text_input("Gemini API Key", type="password")
if api_key:
    genai.configure(api_key=api_key, transport='rest')
    model = genai.GenerativeModel('gemini-flash-latest')

st.divider()
col1, col2 = st.columns(2)
with col1:
    selected_facility = st.radio("점검 대상 시설", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area("현장 상황 설명", placeholder=placeholder_text, height=220)
with col2:
    source_option = st.radio("사진 방식", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드") if "🖼️" in source_option else None

# 7. AI 분석 버튼 (변별력 강화를 위한 프롬프트 수정)
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not api_key: st.error("API Key를 입력하세요.")
    else:
        with st.spinner("KYWA AI가 정밀 분석 중 입니다...."):
            # 프롬프트에 등급 판정 가이드라인 추가
            prompt = f"""
            시설명: [{selected_facility}], 상황: {user_description}. 
            반드시 다음 JSON 형식을 엄수하세요.
            

            [등급 판정 가이드라인]
            - 모든 상황을 '보통'이나 '높음'으로 판정하지 마십시오.
            - 매우 낮음(1~3점): 사고 가능성이 거의 없는 단순 정리정돈이나 가벼운 불편 사항.
            - 낮음(4~6점): 주의가 필요하나 큰 부상으로 이어지지 않는 경미한 사항.
            - 보통(8~12점): 치료가 필요한 부상 위험이 있는 경우.
            - 높음(15점 이상): 골절, 중상 등 심각한 사고 위험이 있는 경우.

            1. p(빈도), s(강도)는 1~5 정수. (경미한 사안은 p, s를 1~2로 낮게 책정)
            2. score는 p*s 결과 숫자.
            3. grade는 "매우 낮음", "낮음", "보통", "높음" 중 하나.
            4. 모든 문장은 명사형 종결.
            5. 관련근거는 법령이나 규칙 명시.
            키: category, scenario, p, s, score, grade, law, solution
            """
            content = [prompt]
            if img_file: content.append(Image.open(img_file))
            try:
                # temperature를 0.0으로 설정하여 일관성 유지
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.rerun()
            except Exception as e: st.error(f"오류: {e}")

# 8. 결과 표시 및 데이터 처리 (점수 기반 등급 재조정 로직 추가)
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    
    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'
    
    processed_data = []
    for item in st.session_state.analysis_results:
        if isinstance(item, dict):
            # 점수(score)를 기반으로 등급을 한 번 더 정밀하게 분류 (Python 로직)
            p_val = int(item.get('p', 3))
            s_val = int(item.get('s', 3))
            score = p_val * s_val
            item['score'] = score # 계산 일치 확인
            
            if score <= 3: refined_grade = "매우 낮음"
            elif score <= 6: refined_grade = "낮음"
            elif score <= 12: refined_grade = "보통"
            else: refined_grade = "높음"
            
            item['grade'] = refined_grade
            
            # 등급별 색상 클래스 매칭
            grade_class = "grade-high" if "높음" in refined_grade else "grade-medium" if refined_grade == '보통' else "grade-low"
            sol_html = str(item.get('solution', '')).replace('\n', '<br>')
            
            table_html += f'<tr><td style="text-align:center">{item.get("category")}</td><td>{item.get("scenario")}</td>'
            table_html += f'<td style="text-align:center">{p_val}</td><td style="text-align:center">{s_val}</td>'
            table_html += f'<td style="text-align:center">{score}</td><td class="{grade_class}">{refined_grade}</td>'
            table_html += f'<td>{item.get("law")}</td><td>{sol_html}</td></tr>'
            processed_data.append(item)
    
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

# 9. 최종 데이터 전송 (추출된 ID 반영)
    if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
        with st.spinner("데이터를 전송 중입니다..."):
            try:
                # 폼 응답 URL
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLScGuW2xT1BU5BKas0NkmADv1BCEX6R3JtQaJ5Nm30iBwGe1rA/formResponse"
                
                success_count = 0
                for row in processed_data:
                    # 추출된 ID와 데이터 매핑
                    payload = {
                        "entry.1902283977": selected_facility,      # 시설명
                        "entry.1485620273": row.get("category"),    # 유해위험요인 (분류)
                        "entry.2072170485": row.get("scenario"),    # 위험상황
                        "entry.1212734944": row.get("grade"),       # 위험등급
                        "entry.2124342735": row.get("solution"),    # 감소대책
                        "entry.543223131": row.get("law")           # 관련근거
                    }
                    
                    # 전송
                    response = requests.post(form_url, data=payload)
                    if response.status_code == 200:
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"총 {success_count}건의 데이터가 KYWA 안전센터로 전송되었습니다!")
                    st.balloons()
                else:
                    st.error("전송에 실패했습니다. 응답 상태를 확인하세요.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # 10. 하단 저장 섹션
    if processed_data:
        st.write("---")
        st.caption("📂 결과 보고서 저장 (Word, Excel)")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "Word 저장", 
                data=create_docx(processed_data), 
                file_name=f"KYWA_Report_{selected_facility}.docx", 
                use_container_width=True
            )
        with dl_col2:
            st.download_button(
                "Excel 저장", 
                data=create_excel(processed_data), 
                file_name=f"KYWA_Data_{selected_facility}.xlsx", 
                use_container_width=True
            )

-----------

현재까지의 코드는 이렇게 구성되어 있어.
이 상태에서 아래 내용만 바꿔서 구성하려고 해.
구글폼에서 종합하는 내용은 아래 내용이 잘 반영되면 수정할 예정이야.

1. 항목 변경
  - 변경전 : 성명/시설명/유해위험요인/위험상황/위험등급/감소대책/관련근거/사진 기록
  - 변경후 : 시설명/부서명/유해위험요인/위험상황/위험등급/감소대책/관련근거/사진 기록
2. 부서명: 드롭다운 형식으로 선택
  - 드롭다운 선택지: 활동부/협력부/청렴감사실/기획혁신부/인재경영부/홍보전략부/안전경영부/재무회계부/디지털정보부/미래활동부/정책사업부/활동안전부/활동인증부/청소년성장지원부/지도인력양성부/지도인력개발부

종합하면, '성명' 입력란은 삭제하고, 첫 선택지는 점검 대상 시설(라디오박스 유지) 이고 부서 선택(드롭다운 형식), 현장 상황 설명(텍스트 장문형으로 입력), 사진방식(카메라/갤러리/없음 중 선택 유지), 그 아래부터는 그대로 유지할거야. KYWA AI 위험요인 분석 시작 등등
