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
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
import plotly.express as px  # 대시보드용 추가

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# --- 데이터 로드 함수 (대시보드용) ---
@st.cache_data(ttl=60)  # 1분마다 캐시 갱신
def load_dashboard_data():
    # 구글 시트의 CSV 내보내기 링크 (본인의 시트 ID로 교체 필요)
    # 아래는 예시 포맷입니다. 실제 시트의 '웹에 게시' -> 'CSV' 링크를 입력하세요.
    SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS7Y8YF9L8Zf_G-rL6Uf_X8n7lWv8_X9I0R2P7-J_X1F6Y5U7z0Z/pub?output=csv"
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        if '타임스탬프' in df.columns:
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'])
        return df
    except Exception as e:
        return None

# [기존 로고 및 헤더 스타일/코드 동일...]
# (중략 - 기존 코드 유지)

# # 1. 현장 상황 설명 중복 제거 (수정됨)
# 6. 입력 섹션
col1, col2 = st.columns(2)

with col1:
    st.markdown("### **🏢 점검 대상 시설**")
    selected_facility = st.radio(
        "시설명 선택", 
        ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], 
        horizontal=True,
        label_visibility="collapsed",
        key="facility_val" 
    )
    
    st.write("") 

    st.markdown("### **📂 담당 부서 선택**")
    dept_list = ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "미래활동부", "정책사업부", "활동안전부", "활동인증부", "청소년성장지원부", "지도인력양성부", "지도인력개발부", "자회사"]
    
    selected_dept = st.selectbox(
        "부서명 선택", 
        dept_list,
        label_visibility="collapsed",
        key="dept_val"
    )
    
    st.write("") 
    # 중복되었던 부분을 삭제하고 하나로 통합했습니다.
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area(
        "상황 설명 입력", 
        placeholder=placeholder_text, 
        height=150,
        label_visibility="collapsed",
        key="user_desc"
    )

with col2:
    st.markdown("### **📸 사진 기록 방식**")
    source_option = st.radio(
        "사진 방식 선택", 
        ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    if "📷" in source_option:
        img_file = st.camera_input("📸 현장 사진 촬영")
    elif "🖼️" in source_option:
        img_file = st.file_uploader("🖼️ 사진 파일 업로드", type=['png', 'jpg', 'jpeg'])
    else:
        img_file = None

# (중략 - AI 분석 실행 및 결과 표시 섹션 기존 코드 유지)

# # 2. 데이터 전송 완료 문구 수정 (수정됨)
if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
    t_facility = st.session_state.facility_val
    t_dept = st.session_state.dept_val

    if "final_data" in st.session_state and st.session_state.final_data:
        with st.spinner(f"[{t_dept}] 데이터를 전송 중..."):
            success_count = 0
            for row in st.session_state.final_data:
                params = {
                    "entry.1651948586": t_facility,
                    "entry.1328786382": t_dept,
                    "entry.1297326802": str(row.get("category", "")),
                    "entry.1421719401": str(row.get("scenario", "")),
                    "entry.1752607260": str(row.get("grade", "")),
                    "entry.271461796": str(row.get("solution", "")),
                    "entry.956205828": str(row.get("law", "")),
                    "entry.1058871339": "사진 별도 첨부"
                }
                base_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"
                try:
                    resp = requests.get(base_url, params=params)
                    if resp.status_code == 200:
                        success_count += 1
                except:
                    pass
            
            if success_count > 0:
                # 요청하신 대로 성공 문구 수정
                st.success("KYWA 안전센터로 데이터 전송 완료!")
                st.balloons()

# (중략 - 저장 섹션 기존 코드 유지)

# # 3. 실시간 대시보드 섹션 추가 (수정됨)
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
        
        # 시트 컬럼명 확인 필요 (구글 폼의 질문 제목과 일치해야 함)
        # 만약 '시설명' 컬럼이 있으면 시설별 참여 인원을 산출
        author_col = "담당부서" # 또는 "시설명"
        if author_col in yearly_data.columns:
            m2.metric("참여 부서 수", f"{yearly_data[author_col].nunique()} 개")

        # 4. 그래프 시각화
        g_col1, g_col2 = st.columns(2)
        
        with g_col1:
            # 폼 항목 이름: "유해위험요인 (분류)" 혹은 저장된 컬럼명
            target_col_cat = "유해위험요인" 
            if target_col_cat in yearly_data.columns:
                st.write(f"**{target_col_cat} 현황**")
                fig_pie = px.pie(yearly_data, names=target_col_cat, hole=0.3)
                fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info(f"'{target_col_cat}' 항목의 통계를 생성 중입니다.")

        with g_col2:
            target_col_fac = "시설명" 
            if target_col_fac in yearly_data.columns:
                st.write(f"**{target_col_fac}별 점검 건수**")
                fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
                fac_counts.columns = [target_col_fac, '건수']
                fig_bar = px.bar(fac_counts, x=target_col_fac, y='건수', color=target_col_fac)
                fig_bar.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("📊 데이터 분석을 위해 구글 시트 연결 설정이 필요합니다.")
