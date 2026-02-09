@@ -3,208 +3,302 @@
import json
import requests
import io
import time
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정
st.set_page_config(page_title="KYWA AI 위험성평가 시스템 (V2.5)", layout="wide", page_icon="🚨")
# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# 세션 상태 초기화
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "final_processed_data" not in st.session_state:
    st.session_state.final_processed_data = None

# --- [Data] 구글 시트 대시보드 데이터 로드 ---
SHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=413707311"

def load_dashboard_data():
    try:
        updated_url = f"{SHEET_URL}&t={int(time.time())}"
        df = pd.read_csv(updated_url)
        df.columns = [c.strip() for c in df.columns]
        
        if '타임스탬프' in df.columns:
            df['타임스탬프'] = df['타임스탬프'].str.replace('오전', 'AM').str.replace('오후', 'PM')
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
            df = df.dropna(subset=['타임스탬프'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# --- [Export] 파일 생성 함수 ---

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
    column_mapping = {'category': '분류', 'scenario': '위험상황', 'p': '빈도', 's': '강도', 'score': '점수', 'grade': '등급', 'law': '관련근거', 'solution': '감소대책'}
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
        vals = [item.get('category'), item.get('scenario'), item.get('p'), item.get('s'), item.get('score'), item.get('grade'), item.get('law'), item.get('solution')]
        for idx, v in enumerate(vals):
            row_cells[idx].text = str(v)
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

# --- [UI] 헤더 및 CSS ---
raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
        <a href="https://kywa-safety-check.streamlit.app/" target="_self">
            <img src="{raw_logo_url}" width="200">
        </a>
        <div>
            <h1 style="margin:0;">🚨 KYWA AI 위험성평가 시스템</h1>
            <p style="color: grey; margin:0;">Korea Youth Work Agency - 스마트 안전관리 플랫폼</p>
        </div>
    </div>
    <style>
    .stButton>button {{ width: 100%; border-radius: 8px; font-weight: bold; background-color: #E60012; color: white; height: 3.5em; }}
    .report-table {{ width: 100%; border-collapse: collapse; }}
    .report-table th, .report-table td {{ padding: 10px; border: 1px solid #dee2e6; text-align: left; font-size: 0.9em; }}
    .report-table th {{ background-color: #f8f9fa; }}
    .grade-high {{ background-color: #ffe3e3; color: #b91c1c; font-weight: bold; }}
    .grade-medium {{ background-color: #fff5dc; color: #92400e; }}
    .grade-low {{ background-color: #ebfbee; color: #166534; }}
    </style>
""", unsafe_allow_html=True)

# API 설정
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"], transport='rest')
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("API Key 미설정")
    st.stop()
# 5. 사이드바 및 모델 설정
with st.sidebar:
    api_key = st.text_input("Gemini API Key", type="password")
if api_key:
    genai.configure(api_key=api_key, transport='rest')
    model = genai.GenerativeModel('gemini-flash-latest')

# --- [Input] 입력 섹션 ---
st.divider()
col1, col2 = st.columns(2)
with col1:
    user_name = st.text_input("👤 작성자 성명", placeholder="성명을 입력하세요")
    selected_facility = st.radio("점검 대상 시설", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    user_description = st.text_area("현장 상황 설명", placeholder="위험 상황을 구체적으로 적어주세요.", height=150)

    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area("현장 상황 설명", placeholder=placeholder_text, height=220)
with col2:
    source_option = st.radio("사진 방식", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드") if "🖼️" in source_option else None

# --- [AI Analysis] 분석 로직 ---
if st.button("🚀 AI 위험요인 분석 시작"):
    if not user_name.strip() or (not user_description.strip() and not img_file):
        st.warning("⚠️ 작성자 성명과 분석 내용(글/사진)을 확인해주세요.")
# 7. AI 분석 버튼 (변별력 강화를 위한 프롬프트 수정)
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not api_key: st.error("API Key를 입력하세요.")
    else:
        with st.spinner("KYWA AI가 분석 중..."):
        with st.spinner("KYWA AI가 정밀 분석 중 입니다...."):
            # 프롬프트에 등급 판정 가이드라인 추가
            prompt = f"""
            시설명: [{selected_facility}], 상황: {user_description}.
            반드시 다음 JSON 형식을 엄수하세요. (리스트 형태 [])
            [필수 분류: 보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 재난 안전 중 선택]
            [규칙: 경미한 전도는 강도 1, 빈도 산정은 엄격하게]
            키: category, scenario, p, s, law, solution
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
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.1})
                # temperature를 0.0으로 설정하여 일관성 유지
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.rerun()
            except Exception as e:
                st.error(f"AI 분석 오류: {e}")
            except Exception as e: st.error(f"오류: {e}")

# --- [Result] 결과 표시 및 전송 ---
# 8. 결과 표시 및 데이터 처리 (점수 기반 등급 재조정 로직 추가)
if st.session_state.analysis_results:
    st.subheader(f"📊 {user_name} 님의 분석 결과")
    processed_data = []
    st.markdown("### 📊 분석 결과")

    table_html = '<table class="report-table"><tr><th>분류</th><th>위험상황</th><th>P</th><th>S</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr>'
    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'
    
    processed_data = []
    for item in st.session_state.analysis_results:
        p, s = int(item.get('p', 1)), int(item.get('s', 1))
        score = p * s
        grade = "높음" if score >= 13 else "보통" if score >= 8 else "낮음" if score >= 4 else "매우 낮음"
        item.update({"score": score, "grade": grade})
        processed_data.append(item)
        
        g_cls = "grade-high" if score >= 13 else "grade-medium" if score >= 8 else "grade-low"
        table_html += f'<tr><td>{item["category"]}</td><td>{item["scenario"]}</td><td>{p}</td><td>{s}</td><td>{score}</td><td class="{g_cls}">{grade}</td><td>{item["law"]}</td><td>{item["solution"]}</td></tr>'
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

    table_html += '</table>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    st.session_state.final_processed_data = processed_data

    if st.button("✅ KYWA 안전센터로 데이터 최종 전송"):
        with st.spinner("전송 중..."):
            form_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"
            for row in st.session_state.final_processed_data:
                # [저장된 정보]에 따른 매칭: 시설명(1902283977), 분류(1485620273), 상황(2072170485), 등급(1212734944), 대책(2124342735), 근거(543223131)
                payload = {
                    "entry.1651948586": user_name,
                    "entry.1902283977": selected_facility,
                    "entry.1485620273": row['category'],
                    "entry.2072170485": row['scenario'],
                    "entry.1212734944": row['grade'],
                    "entry.2124342735": row['solution'],
                    "entry.543223131": row['law'],
                    "entry.1058871339": "사진 포함" if img_file else "사진 없음"
                }
                requests.post(form_url, data=payload)
            st.success("데이터 전송 완료!")
            st.balloons()

# --- [Dashboard] 실시간 현황 ---
st.write("---")
dash_df = load_dashboard_data()
if dash_df is not None and not dash_df.empty:
    st.subheader("📊 2026 실시간 안전 점검 대시보드")
    df_2026 = dash_df[dash_df['타임스탬프'].dt.year == 2026]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("올해 누적 건수", f"{len(df_2026)} 건")
    m2.metric("참여 인원", f"{df_2026['작성자 성명'].nunique() if '작성자 성명' in df_2026 else 0} 명")
    m3.metric("최근 점검일", df_2026['타임스탬프'].max().strftime('%Y-%m-%d') if not df_2026.empty else "-")

    c1, c2 = st.columns(2)
    with c1:
        if "유해위험요인" in df_2026.columns:
            fig = px.pie(df_2026, names="유해위험요인", title="위험요인별 분포", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if "시설명" in df_2026.columns:
            fig = px.bar(df_2026['시설명'].value_counts().reset_index(), x='index', y='시설명', title="시설별 점검 빈도", color='index')
            st.plotly_chart(fig, use_container_width=True)

# 하단 저장 버튼
if st.session_state.final_processed_data:
    st.write("---")
    sc1, sc2 = st.columns(2)
    sc1.download_button("📂 Word 보고서 다운로드", create_docx(st.session_state.final_processed_data), f"KYWA_{user_name}.docx")
    sc2.download_button("📂 Excel 데이터 다운로드", create_excel(st.session_state.final_processed_data), f"KYWA_{user_name}.xlsx")

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
