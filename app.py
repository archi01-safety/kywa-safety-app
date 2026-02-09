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
import plotly.express as px

# 1. 환경 설정 및 보안 우회 (필요한 경우)
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "final_data" not in st.session_state:
    st.session_state.final_data = None

# 3. 모델 설정 (Secrets에서 키를 안전하게 가져옴)
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-flash-latest')
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류가 발생했습니다: {e}")
    st.stop()

# --- 도구 함수 (Word/Excel 생성) ---
def create_docx(data):
    doc = Document()
    doc.add_heading('KYWA AI 위험성평가 결과 보고서', 0)
    for item in data:
        doc.add_paragraph(f"분류: {item.get('category')}")
        doc.add_paragraph(f"상황: {item.get('scenario')}")
        doc.add_paragraph(f"등급: {item.get('grade')} (점수: {item.get('score')})")
        doc.add_paragraph(f"대책: {item.get('solution')}")
        doc.add_paragraph("-" * 20)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_excel(data):
    df = pd.DataFrame(data)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return bio.getvalue()

# --- 4. 헤더 디자인 ---
header_col1, header_col2 = st.columns([1, 4])
raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"

with header_col1:
    st.markdown(f'<a href="https://www.kywa.or.kr/main/main.jsp" target="_blank"><img src="{raw_logo_url}" width="250"></a>', unsafe_allow_html=True)

with header_col2:
    st.title("🚨 KYWA AI 위험성평가 시스템")
    st.caption("Korea Youth Work Agency - 스마트 안전관리 플랫폼")

st.divider()

# --- 5. 입력 섹션 ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### **🏢 점검 대상 정보**")
    selected_facility = st.radio("시설명 선택", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    
    dept_list = ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "자회사"]
    selected_dept = st.selectbox("담당 부서 선택", dept_list)
    
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험"
    user_description = st.text_area("상황 설명 입력", placeholder=placeholder_text, height=150)

with col2:
    st.markdown("### **📸 사진 기록 방식**")
    source_option = st.radio("사진 방식 선택", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    
    img_file = None
    if "📷" in source_option:
        img_file = st.camera_input("📸 현장 사진 촬영")
    elif "🖼️" in source_option:
        img_file = st.file_uploader("🖼️ 사진 파일 업로드", type=['png', 'jpg', 'jpeg'])

# --- 6. AI 분석 실행 ---
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
        try:
            with st.spinner(f"✨ KYWA AI가 [{selected_facility}] 시설을 분석 중입니다..."):
                prompt = f"""
                당신은 한국청소년활동진흥원(KYWA)의 안전관리 전문가입니다.
                다음 상황을 분석하여 위험성평가를 실시하십시오.

                [시설 정보]
                - 시설명: {selected_facility}
                - 담당부서: {selected_dept}
                - 현장 상황: {user_description}

                [필수 지시사항]
                1. category(분류): [보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 작업 환경, 기계(설비)적 요인, 전기적 요인, 재난 안전] 중 선택.
                2. p(빈도)와 s(강도)는 1~5 정수. 
                3. 매우 낮음(1~3점), 낮음(4~6점), 보통(8~12점), 높음(15점 이상).
                4. 반드시 다음 JSON 형식(리스트 형태)으로 출력:
                   [{{ "category": "...", "scenario": "...", "p": 0, "s": 0, "score": 0, "grade": "...", "law": "...", "solution": "..." }}]
                """
                
                content = [prompt]
                if img_file:
                    content.append(Image.open(img_file))
                
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                
                # 결과 저장 (리스트 형태 보장)
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.success("✅ 분석 완료!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")

# --- 7. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    
    processed_data = []
    
    # 1. 테이블 스타일 및 헤더 초기화
    table_html = """
    <style>
        .report-table { width:100%; border-collapse: collapse; margin-top: 20px; }
        .report-table th, .report-table td { border: 1px solid #ddd; padding: 12px 8px; text-align: center; }
        .report-table th { background-color: #f8f9fa; color: #333; }
        .grade-high { color: white !important; background-color: #E60012 !important; font-weight: bold; }
        .grade-medium { color: black !important; background-color: #FFD700 !important; font-weight: bold; }
        .grade-low { color: white !important; background-color: #2E8B57 !important; font-weight: bold; }
    </style>
    <table class="report-table">
        <thead>
            <tr>
                <th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th>
            </tr>
        </thead>
        <tbody>
    """

    # 2. 데이터 루프 돌며 행(row) 생성
    for item in st.session_state.analysis_results:
        # 빈도(p), 강도(s) 안전하게 숫자로 변환
        try:
            p = int(item.get('p', 0))
            s = int(item.get('s', 0))
        except (ValueError, TypeError):
            p, s = 0, 0
            
        score = p * s
        
        # 위험 등급 재산정 로직
        if score <= 3: grade = "매우 낮음"
        elif score <= 6: grade = "낮음"
        elif score <= 12: grade = "보통"
        else: grade = "높음"
        
        # 등급별 CSS 클래스 지정
        grade_class = "grade-high" if grade == "높음" else "grade-medium" if grade == "보통" else "grade-low"
        
        table_html += f"""
            <tr>
                <td>{item.get('category', '-')}</td>
                <td style='text-align:left;'>{item.get('scenario', '-')}</td>
                <td>{p}</td><td>{s}</td><td>{score}</td>
                <td class='{grade_class}'>{grade}</td>
                <td>{item.get('law', '-')}</td>
                <td style='text-align:left;'>{item.get('solution', '-')}</td>
            </tr>
        """
        
        # 세션 상태 업데이트를 위한 데이터 저장
        item['score'] = score
        item['grade'] = grade
        processed_data.append(item)

    # 3. 테이블 닫기
    table_html += "</tbody></table>"

    # 4. 🔥 핵심: HTML 렌더링 (이 줄이 반드시 있어야 표로 보입니다)
    st.markdown(table_html, unsafe_allow_html=True)
    
    # 최종 데이터 세션 저장
    st.session_state.final_data = processed_data
    # --- 8. 최종 데이터 전송 및 저장 ---
    st.write("")
    if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
        with st.spinner("데이터 전송 중..."):
            try:
                # 구글 폼 URL (사용자 정보 기반)
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLScGuW2xT1BU5BKas0NkmADv1BCEX6R3JtQaJ5Nm30iBwGe1rA/formResponse"
                
                success_count = 0
                for row in st.session_state.final_data:
                    payload = {
                        "entry.1902283977": selected_facility,
                        "entry.1485620273": row.get("category"),
                        "entry.2072170485": row.get("scenario"),
                        "entry.1212734944": row.get("grade"),
                        "entry.2124342735": row.get("solution"),
                        "entry.543223131": row.get("law")
                    }
                    res = requests.post(form_url, data=payload)
                    if res.status_code == 200:
                        success_count += 1
                
                st.success(f"총 {success_count}건의 데이터가 성공적으로 전송되었습니다!")
                st.balloons()
            except Exception as e:
                st.error(f"전송 실패: {e}")

    # 저장 버튼
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("📂 Word 저장", data=create_docx(st.session_state.final_data), file_name=f"KYWA_{selected_facility}.docx", use_container_width=True)
    with dl_col2:
        st.download_button("📊 Excel 저장", data=create_excel(st.session_state.final_data), file_name=f"KYWA_{selected_facility}.xlsx", use_container_width=True)

# --- [수정] 날짜 형식 오류를 해결한 데이터 로드 함수 ---
def load_dashboard_data():
    # 구글 시트 CSV 내보내기 링크
    sheet_url = "https://docs.google.com/spreadsheets/d/1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q/export?format=csv&gid=413707311"
    
    try:
        df = pd.read_csv(sheet_url)
        
        if '타임스탬프' in df.columns:
            # 1. 한국어 '오전/오후'를 Pandas가 인식 가능한 'AM/PM'으로 변경
            df['타임스탬프'] = df['타임스탬프'].str.replace('오전', 'AM').str.replace('오후', 'PM')
            
            # 2. 날짜 형식으로 변환 (format을 지정하지 않아도 치환 후에는 잘 작동합니다)
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
            
            # 3. 변환 실패한 데이터(NaT) 제거 (선택 사항)
            df = df.dropna(subset=['타임스탬프'])
            
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None

# --- 대시보드 섹션 ---
st.write("---")
dashboard_data = load_dashboard_data()

if dashboard_data is not None:
    # 2. 날짜 필터링 (2026년 데이터만)
    if '타임스탬프' in dashboard_data.columns:
        yearly_data = dashboard_data[dashboard_data['타임스탬프'].dt.year == 2026]
    else:
        yearly_data = dashboard_data

    if yearly_data.empty:
        st.warning("📅 2026년도로 기록된 데이터가 시트에 아직 없습니다. 첫 번째 데이터를 전송해 보세요!")
    else:
        st.subheader("📊 실시간 점검 데이터 현황 (2026년)")
        
        # 3. 상단 지표
        total_count = len(yearly_data)
        m1, m2 = st.columns(2)
        m1.metric("올해 누적 점검 건수", f"{total_count} 건")
        
        # '작성자 성명' 대신 '시설명' 기준으로 참여 분포 확인 (또는 실제 컬럼명으로 수정)
        author_col = "작성자 성명" 
        if author_col in yearly_data.columns:
            m2.metric("참여 인원(명)", f"{yearly_data[author_col].nunique()} 명")
        else:
            m2.metric("점검 시설 종류", f"{yearly_data['시설명'].nunique()} 곳")

# 4. 그래프 시각화
g_col1, g_col2 = st.columns(2)

with g_col1:
    # D열(인덱스 3)을 직접 지정하거나 이름을 확인합니다.
    # 만약 컬럼명이 정확하지 않아도 위치로 찾아낼 수 있도록 안전장치를 추가합니다.
    if len(yearly_data.columns) >= 4:
        # D열의 실제 이름을 가져옵니다.
        target_col_cat = yearly_data.columns[3] 
        
        st.write(f"**{target_col_cat} 현황**")
        # 데이터가 비어있지 않은지 확인 후 그래프 생성
        if not yearly_data[target_col_cat].dropna().empty:
            fig_pie = px.pie(yearly_data, names=target_col_cat, hole=0.3)
            fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("데이터가 충분하지 않아 그래프를 표시할 수 없습니다.")
    else:
        st.error("💡 시트에서 D열(유해위험요인)을 찾을 수 없습니다. 시트 구조를 확인해주세요.")

with g_col2:
    # '시설명' 컬럼 처리 (일반적으로 B열 또는 C열에 위치)
    target_col_fac = "시설명" 
    if target_col_fac in yearly_data.columns:
        st.write(f"**{target_col_fac}별 점검 건수**")
        fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
        fac_counts.columns = [target_col_fac, '건수']
        fig_bar = px.bar(fac_counts, x=target_col_fac, y='건수', color=target_col_fac)
        fig_bar.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        # 시설명도 못 찾을 경우를 대비해 첫 번째 컬럼(A열) 근처를 탐색할 수 있습니다.
        st.info("💡 '시설명' 컬럼 이름을 확인해주세요.")

