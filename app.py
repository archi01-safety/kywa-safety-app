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

# 5. 모델 설정 (Secrets에서 키를 안전하게 가져옴)
try:
    # Streamlit Secrets에 저장된 키를 자동으로 호출합니다.
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-flash-latest') # 또는 사용 중인 모델명
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류가 발생했습니다: {e}")
    st.stop()

# 6. 입력 섹션 (라디오박스/드롭다운 라벨 크기 및 볼드 강조)
col1, col2 = st.columns(2)

with col1:
    # 1. 시설명 선택
    st.markdown("### **🏢 점검 대상 시설**")
    selected_facility = st.radio(
        "시설명 선택", # 가이드용 (숨겨짐)
        ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], 
        horizontal=True,
        label_visibility="collapsed" # 기본 라벨 숨김
    )
    
    st.write("") # 간격 조절

    # 2. 부서명 선택
    st.markdown("### **📂 담당 부서 선택**")
    dept_list = [
        "활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", 
        "안전경영부", "재무회계부", "디지털정보부", "미래활동부", "정책사업부", 
        "활동안전부", "활동인증부", "청소년성장지원부", "지도인력양성부", "지도인력개발부", "자회사"
    ]
    selected_dept = st.selectbox(
        "부서명 선택", 
        dept_list,
        label_visibility="collapsed"
    )
    
    st.write("") # 간격 조절

    # 3. 현장 상황 설명
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area(
        "상황 설명 입력", 
        placeholder=placeholder_text, 
        height=150,
        label_visibility="collapsed"
    )

with col2:
    # 4. 사진 방식 및 입력
    st.markdown("### **📸 사진 기록 방식**")
    source_option = st.radio(
        "사진 방식 선택", 
        ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # 사진 입력 위젯 (이 부분은 위젯 자체가 제목 역할을 하므로 스타일 유지)
    if "📷" in source_option:
        img_file = st.camera_input("📸 현장 사진 촬영")
    elif "🖼️" in source_option:
        img_file = st.file_uploader("🖼️ 사진 파일 업로드", type=['png', 'jpg', 'jpeg'])
    else:
        img_file = None
        
# 7. AI 분석 실행 섹션
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
        try:
            with st.spinner(f"✨ KYWA AI가 [{selected_facility}] 시설의 데이터를 분석 중입니다...🔍"):
                
                # 모든 지침을 하나의 prompt 문자열 안에 포함시킵니다.
                prompt = f"""
                당신은 한국청소년활동진흥원(KYWA)의 안전관리 전문가입니다.
                
                [시설 정보]
                - 시설명: {selected_facility}
                - 담당부서: {selected_dept}
                - 현장 상황: {user_description}

                [필수 지시사항]
                1. category(분류): 시설명이 '생태', '해양' 등이라 하더라도 이를 category에 적지 마십시오. 
                   반드시 [보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 작업특성 요인, 작업환경 요인, 작업 환경, 기계(설비)적 요인, 전기적 요인, 재난 안전] 중 상황에 가장 적합한 표준 분류를 선택하십시오.
                2. 등급 판정의 객관성: 단순 노후화나 경미한 파손(예: 보도블럭 일부 들뜸/파손)은 강도(s)를 2 이하로 설정하여 전체 score가 6점 이하가 되도록 하십시오.

                [빈도 등급 판정 가이드라인] ※1~5번 기준과 예를 근거로 하되 안전수칙 및 작업표준은 있음을 전제로 등급 판정.
                1. 빈도 5점(기준: 피해가 발생할 가능성이 매우 높음)
                2. 빈도 4점(기준: 피해가 발생할 가능성이 높음)
                3. 빈도 3점(기준: 부주의하면 피해가 발생할 가능성이 있음)
                4. 빈도 2점(기준: 피해가 발생할 가능성이 낮음)
                5. 빈도 1점(기준: 피해가 발생할 가능성이 매우 낮음)

                [강도 등급 판정 가이드라인]
                1. 강도 4점(사망 또는 영구 장애), 3점(중대한 부상/휴업 수반), 2점(응급처치 이상/비휴업), 1점(경미한 부상)

                [판정 원칙 및 예외 기준]
                1. 일상적 위험 vs 산업적 위험 구분: 단순 전도 등은 강도 1점을 원칙으로 함.
                2. 점수 조정 예시: 보도블럭 파손(빈도 2, 강도 1 -> 2점), 바닥 물기(빈도 3, 강도 1 -> 3점)

                [종합 등급 판정 가이드라인]
                - 매우 낮음(1~3점), 낮음(4~6점), 보통(8~12점), 높음(15점), 매우 높음(16~20점)
                - 모든 문장은 명사형 종결.
                - 반드시 다음 JSON 형식을 엄수하세요: 키는 category, scenario, p, s, score, grade, law, solution 이며 리스트 [] 안에 담아 출력하세요.
                """

                # 분석 데이터 준비
                content = [prompt]
                if img_file:
                    from PIL import Image
                    content.append(Image.open(img_file))
                
                # 모델 호출 및 결과 처리
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                
                # 결과 저장 및 리프레시
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.success(f"✅ [{selected_facility}] 시설 분석 완료!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# 8. 결과 표시
if st.session_state.analysis_results:
    # [수정] user_name을 삭제하고 시설명/부서명으로 변경하여 NameError 방지
    st.markdown(f"### 📊 [{selected_facility}] {selected_dept} 위험성 분석 결과")
    
    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'
    st.session_state.final_processed_data = []
    
    for item in st.session_state.analysis_results:
        # 데이터 안전하게 가져오기 (기본값 설정)
        p_val = int(item.get('p', 1))
        s_val = int(item.get('s', 1))
        score = p_val * s_val
        
        # 위험 등급 재계산 로직 유지
        if score <= 3: refined_grade = "매우 낮음"
        elif score <= 6: refined_grade = "낮음"
        elif score <= 12: refined_grade = "보통"
        elif score <= 15: refined_grade = "높음"
        else: refined_grade = "매우 높음"
        
        item['grade'] = refined_grade
        item['score'] = score
        
        # 등급별 CSS 클래스 매칭
        if "매우 높음" in refined_grade or "높음" in refined_grade:
            grade_class = "grade-high"
        elif refined_grade == '보통':
            grade_class = "grade-medium"
        else:
            grade_class = "grade-low"
        
        # 테이블 행 생성
        table_html += f'<tr><td style="text-align:center">{item.get("category", "-")}</td><td>{item.get("scenario", "-")}</td>'
        table_html += f'<td style="text-align:center">{p_val}</td><td style="text-align:center">{s_val}</td>'
        table_html += f'<td style="text-align:center">{score}</td><td class="{grade_class}" style="text-align:center">{refined_grade}</td>'
        table_html += f'<td>{item.get("law", "-")}</td><td>{str(item.get("solution", "-")).replace(chr(10), "<br>")}</td></tr>'
        
        st.session_state.final_processed_data.append(item)
    
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    
    # 추가: 분석 결과 초기화 버튼 (선택 사항)
    if st.button("🔄 분석 결과 지우기"):
        st.session_state.analysis_results = []
        st.rerun()

# 9. 최종 데이터 전송 (부서명 반영)
    if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
        with st.spinner("🛰️ 데이터를 전송 중입니다..."):
            try:
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLScGuW2xT1BU5BKas0NkmADv1BCEX6R3JtQaJ5Nm30iBwGe1rA/formResponse"
                success_count = 0
                for row in processed_data:
                    payload = {
                        "entry.1902283977": selected_facility,      # 시설명
                        "entry.XXXXXXXXXX": selected_dept,          # ★ 부서명 (구글 폼에서 새로 확인한 ID를 여기에 넣으세요)
                        "entry.1485620273": row.get("category"),    # 분류
                        "entry.2072170485": row.get("scenario"),    # 위험상황
                        "entry.1212734944": row.get("grade"),       # 위험등급
                        "entry.2124342735": row.get("solution"),    # 감소대책
                        "entry.543223131": row.get("law")           # 관련근거
                    }
                    response = requests.post(form_url, data=payload)
                    if response.status_code == 200:
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"총 {success_count}건의 데이터가 KYWA 안전센터로 전송되었습니다!")
                    st.balloons()
            except Exception as e:
                st.error(f"전송 오류: {e}")

# 10. 하단 저장 섹션 (오류 수정본)
if st.session_state.analysis_results: # 분석 결과가 있을 때만 표시
    st.write("---")
    st.markdown("### **📂 결과 보고서 저장 (Word, Excel)**")
    
    # 9번 단계에서 생성된 processed_data를 사용하여 파일 생성
    # 만약 버튼 클릭 시 오류가 난다면, processed_data가 정의된 영역 안에서 실행되어야 합니다.
    
    dl_col1, dl_col2 = st.columns(2)
    
    # 파일명에서 user_name을 삭제하고 selected_dept를 넣었습니다.
    file_prefix = f"KYWA_{selected_facility}_{selected_dept}"
    
    with dl_col1:
        st.download_button(
            label="📄 Word 보고서 저장", 
            data=create_docx(processed_data), 
            file_name=f"{file_prefix}.docx", 
            use_container_width=True
        )
        
    with dl_col2:
        st.download_button(
            label="📊 Excel 데이터 저장", 
            data=create_excel(processed_data), 
            file_name=f"{file_prefix}.xlsx", 
            use_container_width=True
        )




