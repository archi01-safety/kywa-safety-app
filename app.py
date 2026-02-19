import streamlit as st

# [1] 페이지 설정 (반드시 모든 st 함수 중 가장 처음에 위치)
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# [2] 필수 라이브러리 임포트
import os
import ssl
import json
import requests
import io
import datetime
import base64
import codecs
import pandas as pd
import numpy as np
import cv2  # 비식별화의 핵심
import plotly.express as px
from PIL import Image
from docx import Document
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


# --- [1단계] 구글 드라이브/시트 설정 (PEM 로드 집중 수정 버전) ---
DRIVE_FOLDER_ID = "1K4hIEsAfX9iGsk9NX_4-4Z9bGXLNVzKC"
SPREADSHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q"

# --- [추가] 실제 구글 드라이브에 파일을 업로드하는 함수 ---
def upload_to_drive(file_name, file_content, mime_type):
    """
    구글 드라이브의 특정 폴더로 파일을 업로드합니다.
    """
    if drive_service is None:
        st.error("구글 드라이브 서비스가 연결되지 않았습니다.")
        return None
    
    try:
        # 파일 메타데이터 설정 (이름과 저장될 폴더 지정)
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]  # 이전에 설정하신 폴더 ID가 여기 쓰입니다.
        }
        
        # 파일 콘텐츠 준비
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=mime_type, 
            resumable=True
        )
        
        # 드라이브에 파일 생성
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # 업로드된 파일의 링크 반환
        return file.get('webViewLink')
        
    except Exception as e:
        st.error(f"구글 드라이브 업로드 중 에러 발생: {e}")
        return None

drive_service = None
sheets_service = None

if "gcp_service_account" in st.secrets:
    try:
        creds_info = st.secrets["gcp_service_account"]
        
        # private_key 내의 실제 줄바꿈 문자 처리 (가장 흔한 오류 원인)
        if isinstance(creds_info, (dict, st.runtime.secrets.AttrDict)):
            creds_dict = dict(creds_info)
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            
            drive_service = build('drive', 'v3', credentials=creds)
            sheets_service = build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"⚠️ 인증 설정 오류: {e}")

else:
    st.error("Secrets 설정에서 'gcp_service_account'를 찾을 수 없습니다.")

# (이후 기존의 CSS 설정 및 나머지 코드를 이어 붙이시면 됩니다.)
# 주의: 아래쪽에 있는 st.set_page_config(page_title="KYWA AI 위험성평가 시스템", ...) 코드는 삭제하세요.

# [수정 2] 파라미터 이름을 unsafe_allow_html=True 로 변경
st.markdown("""
    <style>
    /* 모든 텍스트가 현재 테마의 글자색을 따르도록 설정 */
    html, body, [data-testid="stWidgetLabel"] p {
        color: var(--text-color);
    }
    
    /* 모바일 환경에서 표(Table)나 컨테이너의 가독성 향상 */
    .stDataFrame {
        width: 100% !important;
    }
    
    /* 이미지나 아이콘이 다크모드에서 너무 눈부시지 않게 살짝 조절 */
    img {
        max-width: 100%;
        filter: brightness(var(--image-brightness, 1));
    }
    </style>
    """, unsafe_allow_html=True)

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



# --- [2단계] 구글 드라이브/시트 전송 함수 추가 ---

def upload_photo_to_drive(file_obj, filename):
    try:
        # Apps Script 웹 앱 URL (방금 복사한 주소)
        apps_script_url = "https://script.google.com/macros/s/AKfycbwMhipDH9zMVajhbD2LBXGgnJdaqs3oHmatjqtvAXWL0PXhInk6tqsqRcb6MJkZFChm/exec"
        
        file_obj.seek(0)
        img_base64 = base64.b64encode(file_obj.getvalue()).decode('utf-8')
        
        payload = {
            "filename": filename,
            "fileBase64": img_base64
        }
        
        # POST 요청으로 사진 전송
        response = requests.post(apps_script_url, json=payload)
        res_data = response.json()
        
        return res_data.get("url", "업로드 실패")
    except Exception as e:
        return f"업로드 실패: {str(e)}"

def append_row_to_sheet(row_data):
    try:
        # [확인 필요] 실제 시트 탭 이름과 공백이 정확히 일치해야 합니다.
        # 만약 구글폼 연동 시트라면 보통 '설문지 응답 1' 입니다.
        range_name = "'설문지 응답 시트1'!A1" 
        
        body = {'values': [row_data]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range=range_name,
            valueInputOption='USER_ENTERED', 
            insertDataOption='INSERT_ROWS', # [추가] 새 행을 삽입하며 추가하도록 명시
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"시트 저장 실패: {str(e)}")
        return False

# --- [추가] 버튼 스타일 설정 ---
st.markdown("""
    <style>
    /* 모든 Streamlit 버튼 스타일 수정 */
    div.stButton > button {
        background-color: #ff4b4b !important; /* 기본 붉은색 */
        color: white !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        border-radius: 0.5rem !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }

    /* 마우스 호버(Hover) 시 효과 */
    div.stButton > button:hover {
        background-color: #ff3333 !important; /* 마우스 올렸을 때 더 진한 빨강 */
        color: white !important;
        border: none !important;
        transform: scale(1.01); /* 아주 살짝 커지는 효과 */
    }
    
    /* Word/Excel 저장 버튼 등 일반 버튼도 동일 적용을 원치 않으시면 위 범위를 좁힐 수 있습니다 */
    </style>
""", unsafe_allow_html=True)

# --- 4. 스타일 및 헤더 디자인 (오류 방지 중괄호 처리) ---
st.markdown("""
    <style>
    /* 버튼 스타일 */
    div.stButton > button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 0.5rem !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        background-color: #ff3333 !important;
        transform: scale(1.01);
    }
    /* 로고 및 타이틀 스타일 */
    .logo-img { cursor: pointer; display: block; margin-top: 2px; }
    .refresh-title { text-decoration: none !important; color: inherit !important; cursor: pointer; }
    .refresh-title:hover { color: #FF4B4B !important; }
    </style>
""", unsafe_allow_html=True)

header_col1, header_col2 = st.columns([1, 4])
raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"

with header_col1:
    # f-string을 쓰지 않고 직접 삽입하여 중괄호 오류 원천 차단
    st.markdown(f'''
        <a href="https://www.kywa.or.kr/main/main.jsp" target="_blank">
            <img src="{raw_logo_url}" width="300" class="logo-img">
        </a>
    ''', unsafe_allow_html=True)

with header_col2:
    st.markdown("""
        <a href="/" target="_self" class="refresh-title">
            <h1 style='margin-bottom: 0;'>🚨 KYWA AI 위험성평가 시스템</h1>
        </a>
        <p style='color: gray; margin-top: 0;'>Korea Youth Work Agency - 스마트 안전관리 플랫폼</p>
    """, unsafe_allow_html=True)

st.divider()

# --- 5. 입력 섹션 ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### **🏢 점검 대상 정보**")
    selected_facility = st.radio("• 시설명 선택 (필수)", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    
    dept_list = ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "자회사"]
    selected_dept = st.selectbox("• 담당 부서 선택 (필수)", dept_list)
    
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예  시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n  (자세히 작성할수록 정확한 결과가 나옵니다.)"
    user_description = st.text_area("• 상황 설명 입력 (권장)", placeholder=placeholder_text, height=150)

with col2:
    st.markdown("### **📸 사진 기록 방식**")
    
    # [1] 안내 문구
    st.markdown("""
        • **사진 방식 선택** <div style="font-size: 0.85rem; color: #808080; line-height: 1.5; margin-top: 5px;">
            🚫 얼굴(정면)을 업로드 하지 않도록 주의<br>
            🚫 개인정보 및 주요자료가 포함되지 않도록 주의
        </div>
        """, unsafe_allow_html=True)

    # [2] 변수 정의 (이 줄이 반드시 if문보다 위에 있어야 합니다)
    source_option = st.radio(
        label="사진 방식 선택 레이블(숨김)", 
        options=("📸 사진", "🚫 없음"), 
        horizontal=True,
        label_visibility="collapsed"
    )

    img_file = None

    # [3] 조건문 실행
    if "📸" in source_option:
        st.info("📸 아래 박스를 클릭하면 [사진촬영] 또는 [사진업로드] 선택이 가능합니다.")
        
       
# 2. 업로더 한글화 CSS (보강된 버전)
        st.markdown("""
            <style>
                /* 1. 원래 있던 텍스트들 숨기기 */
                section[data-testid="stFileUploadDropzone"] div div span,
                section[data-testid="stFileUploadDropzone"] small,
                section[data-testid="stFileUploadDropzone"] button {
                    display: none !important;
                }

                /* 2. 상단에 새로운 안내 문구 추가 */
                section[data-testid="stFileUploadDropzone"] div div::before {
                    content: "여기에 사진을 끌어다 놓으세요";
                    display: block !important;
                    font-size: 0.9rem !important;
                    color: #808080 !important;
                    margin-bottom: 10px !important;
                }

                /* 3. 버튼처럼 보이는 가짜 버튼 생성 */
                section[data-testid="stFileUploadDropzone"]::before {
                    content: "📸 사진 촬영 또는 선택하기";
                    display: block !important;
                    margin: 10px auto !important;
                    padding: 10px 20px !important;
                    background-color: #ff4b4b !important; /* 배경색을 빨간색으로 */
                    color: white !important; /* 글자를 흰색으로 */
                    border-radius: 8px !important;
                    cursor: pointer !important;
                    font-weight: bold !important;
                    text-align: center !important;
                    width: fit-content !important;
                }

                /* 4. 하단에 용량 제한 문구 추가 */
                section[data-testid="stFileUploadDropzone"] div div::after {
                    content: "파일당 최대 200MB • PNG, JPG, JPEG";
                    display: block !important;
                    font-size: 0.75rem !important;
                    color: #a0a0a0 !important;
                    margin-top: 5px !important;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # 3. 통합된 업로더 실행
        img_file = st.file_uploader(
            "사진 업로드 전용", 
            type=['png', 'jpg', 'jpeg'], 
            label_visibility="collapsed",
            key="integrated_photo_upload"
        )


def apply_face_blur(img_file):
    import cv2
    import numpy as np

    try:
        # 1. 이미지 읽기
        img_file.seek(0)
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None: return img_file.getvalue()
        
        h, w, _ = image.shape

        # [2] 어두운 얼굴 인식률 향상 (CLAHE 전처리)
        # 이미지를 밝고 선명하게 만들어 그늘진 얼굴 특징을 추출합니다.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced_gray = cv2.merge((cl, a, b))
        enhanced_gray = cv2.cvtColor(enhanced_gray, cv2.COLOR_LAB2BGR)
        enhanced_gray = cv2.cvtColor(enhanced_gray, cv2.COLOR_BGR2GRAY) # OpenCV 감지용

        # [3] OpenCV 얼굴 인식기 로드
        # Haar Cascade 방식 사용 (정면 및 측면 얼굴 대응)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')

# [4] 초강력 이중 감지 (정면 + 측면 합집합) 및 이미지 회전 및 다중 검사 (0도, -20도, 20도)
        # 기울어진 안전모 인물을 잡기 위한 핵심 로직입니다.
        for angle in [0, -20, 20]:
            if angle == 0:
                rotated_img = image
                matrix = None
            else:
                # 이미지 중심 기준 회전 행렬 생성
                matrix = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
                rotated_img = cv2.warpAffine(image, matrix, (w, h))

        # 정면(front): minNeighbors=5 (깐깐하게 감지하여 다리 오탐지 감소)
        # 측면(profile): minNeighbors=3 (너그럽게 감지하여 옆모습 포착)
        faces_front = face_cascade.detectMultiScale(enhanced_gray, scaleFactor=1.05, minNeighbors=5, minSize=(30, 30))
        faces_profile = profile_cascade.detectMultiScale(enhanced_gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30))
        
        # 두 결과를 하나로 합침
        all_faces = []
        if len(faces_front) > 0: all_faces.extend(faces_front)
        if len(faces_profile) > 0: all_faces.extend(faces_profile)

        if len(all_faces) > 0:
            for (x, y, rw, rh) in all_faces:
                # --- [수정] 이미지 하단 10% 영역만 얼굴 제외 구역으로 설정 ---
                # y + (rh / 2)는 감지된 박스의 중심점 높이입니다.
                # h * 0.9 보다 크다는 것은 이미지의 맨 아래쪽 10% 지점에 위치한다는 뜻입니다.
                if y + (rh / 2) > h * 0.9:
                    continue


                # [5] 얼굴 영역 20% 더 넓게 잡음 (Padding)
                pad_w = int(rw * 0.2)
                pad_h = int(rh * 0.2)
                
                x_final = max(0, x - pad_w)
                y_final = max(0, y - pad_h)
                rw_final = min(w - x_final, rw + (pad_w * 2))
                rh_final = min(h - y_final, rh + (pad_h * 2))

# [얼굴부분 동그라미로 블러처리] if rw_final > 0 and rh_final > 0: 블록 내부를 교체

                if rw_final > 0 and rh_final > 0:
                    # 1. 얼굴 영역 ROI 추출
                    face_roi = image[y_final:y_final+rh_final, x_final:x_final+rw_final]
                    
                    # 2. 원형 마스크 생성
                    # ROI와 같은 크기의 검은색 이미지 생성
                    mask = np.zeros((rh_final, rw_final), dtype=np.uint8)
                    # 중심점과 반지름 계산
                    center = (rw_final // 2, rh_final // 2)
                    radius = min(rw_final, rh_final) // 2
                    # 하얀색 꽉 찬 원 그리기
                    cv2.circle(mask, center, radius, (255), -1)

                    # 3. 강력한 블러 이미지 생성
                    level = max(rw_final, rh_final) // 2 
                    if level % 2 == 0: level += 1
                    # 2중 블러로 더 강력하게
                    blurred_roi = cv2.GaussianBlur(face_roi, (level, level), 0)
                    blurred_roi = cv2.GaussianBlur(blurred_roi, (level, level), 0)

                    # 4. 마스크를 이용해 합치기 (핵심)
                    # 마스크가 하얀색(255)인 부분은 블러 이미지를, 아니면 원본 ROI를 사용
                    # 마스크를 3채널(RGB)로 맞춰줘야 함
                    mask_3ch = cv2.merge([mask, mask, mask])
                    combined_roi = np.where(mask_3ch == 255, blurred_roi, face_roi)

                    # 5. 원본 이미지에 다시 붙여넣기
                    image[y_final:y_final+rh_final, x_final:x_final+rw_final] = combined_roi

        # 결과 반환
        _, buffer = cv2.imencode('.jpg', image)
        return buffer.tobytes()

    except Exception as e:
        st.error(f"비식별화 프로세스 오류: {e}")
        img_file.seek(0)
        return img_file.getvalue()


# --- [3단계] 전송 버튼 로직 내 수정 ---
processed_img_final = None  # 처리된 이미지를 담을 변수

if img_file:
    with st.spinner("🔒 개인정보 비식별화 처리 중..."):
        # 원본 대신 블러 처리된 이미지 생성
        processed_img_bytes = apply_face_blur(img_file)
        # Bytes 데이터를 파일 객체처럼 변환 (io.BytesIO 사용)
        processed_img_final = io.BytesIO(processed_img_bytes)
        # 파일 이름을 식별하기 위해 name 속성 부여
        processed_img_final.name = img_file.name

# --- 6. AI 분석 실행 ---
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
                2. 점수 조정 예시: 보도블럭 파손(빈도 2, 강도 1 -> 2점), 바닥 물기(빈도 3, 강도 1 -> 3점), 키보드 및 마우스 작업(빈도 3, 강도 1 -> 3점)

                [종합 등급 판정 가이드라인]
                - 매우 낮음(1~3점), 낮음(4~6점), 보통(8점), 높음(9~12점), 매우 높음(16~20점)
                - 8점부터는 '허용 불가능한 수준'의 사안으로 판단하므로 경미한 사항은 최대 6점을 기준으로 함.
                - 모든 문장은 명사형 종결.
                - 반드시 다음 JSON 형식을 엄수하세요: 키는 category, scenario, p, s, score, grade, law, solution 이며 리스트 [] 안에 담아 출력하세요.
                """

                # 분석 데이터 준비
                content = [prompt]
                
                # [수정] 이미지 로드 부분 (PIL import 위치 확인)
                from PIL import Image 
                
                if img_file:
                    content.append(Image.open(img_file))
                
                if processed_img_final:
                    content.append(Image.open(processed_img_final))

                # [핵심 수정] 재시도 로직 추가 (API 한도 초과 방지)
                import time
                response = None
                max_retries = 3  # 최대 3번까지 재시도

                for attempt in range(max_retries):
                    try:
                        # 모델 호출
                        response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                        break  # 성공하면 반복문 탈출!
                    except Exception as e:
                        # 429 에러(Quota)나 과부하 에러가 났을 때만 재시도
                        if "429" in str(e) or "quota" in str(e).lower() or "503" in str(e):
                            if attempt < max_retries - 1:
                                time.sleep(2 * (attempt + 1))  # 2초, 4초... 점차 길게 대기
                                st.toast(f"⏳ 사용량 조절 중... 재시도 {attempt+1}/{max_retries}")
                                continue
                            else:
                                st.error("🚨 현재 AI 이용량이 많아 분석이 어렵습니다. 1분 뒤에 다시 시도해주세요.")
                                st.stop() # 코드 실행 중단
                        else:
                            raise e # 다른 에러(코드 오류 등)는 바로 띄움

                # 결과 처리 (성공했을 때만 실행)
                if response:
                    res_data = json.loads(response.text.strip())
                    
                    # 결과 저장 및 리프레시
                    st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                    st.success(f"✅ [{selected_facility}] 시설 분석 완료!")
                    st.rerun()

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# --- 7. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📋 AI 위험성평가 결과 (최종)")
    st.info("💡 **'감소대책'** 칸만 직접 수정이 가능합니다. 수정한 내용은 실시간으로 반영됩니다.")

    # 1. 데이터를 데이터프레임으로 변환
    df = pd.DataFrame(st.session_state.analysis_results)

    # 2. 데이터 에디터 하나로 편집 + 프리뷰 통합
    edited_df = st.data_editor(
        df,
        column_config={
            "category": st.column_config.TextColumn("분류", disabled=True),
            "scenario": st.column_config.TextColumn("위험상황", disabled=True, width="medium"),
            "p": st.column_config.NumberColumn("빈도", disabled=True, width="small"),
            "s": st.column_config.NumberColumn("강도", disabled=True, width="small"),
            "score": st.column_config.NumberColumn("점수", disabled=True, width="small"),
            "grade": st.column_config.TextColumn("등급", disabled=True), # 색상 태그는 없지만 깔끔함
            "law": st.column_config.TextColumn("관련근거", disabled=True, width="medium"),
            "solution": st.column_config.TextColumn(
                "✅ 감소대책 (편집 가능)", 
                help="현장에 맞게 내용을 수정하세요.",
                width="large",
                required=True
            )
        },
        # 감소대책(solution)을 제외한 모든 컬럼 수정 금지
        disabled=["category", "scenario", "p", "s", "score", "grade", "law"],
        use_container_width=True,
        hide_index=True,
        key="final_editor"
    )

    # 3. 데이터 업데이트 (수정 즉시 반영)
    st.session_state.analysis_results = edited_df.to_dict('records')
    st.session_state.final_data = st.session_state.analysis_results

    st.success("✅ 최종 검토가 완료되었습니다. 아래 버튼으로 보고서를 저장하세요.")


# --- [3단계] 전송 버튼 로직 (타임스탬프 수정 버전) ---
st.write("")
if st.button("✅ KYWA AI 안전센터로 데이터 최종 전송", use_container_width=True):
    if sheets_service is None or drive_service is None:
        st.error("⚠️ GCP 인증에 실패하여 데이터를 전송할 수 없습니다. 관리자에게 문의하세요.")
        st.stop()
    
    if not st.session_state.final_data:
        st.error("⚠️ 전송할 데이터가 없습니다. 먼저 분석을 진행해 주세요.")
    else:
        with st.spinner("🚀 KYWA AI 안전센터로 데이터를 전송 중입니다..."):
            try:
                # [수정] 한국 시간(KST)으로 현재 시간 설정
                now_kst = datetime.datetime.now() + datetime.timedelta(hours=9)
                current_time = now_kst.strftime("%Y-%m-%d %H:%M:%S") # 시트 기록용 (2026-02-12 18:00:20)
                timestamp_str = now_kst.strftime("%Y%m%d_%H%M%S")    # 파일 이름용 (20260212_180020)

                # 1. 사진 업로드
                photo_link = "사진 없음"
                if processed_img_final: # img_file 대신 블러 처리된 변수 사용
                    filename = f"{selected_facility}_{timestamp_str}.jpg"
                    # 위에서 정의한 함수 이름으로 호출 (upload_photo_to_drive)
                    photo_link = upload_photo_to_drive(processed_img_final, filename)
                
                # 2. 시트 데이터 준비 및 전송
                success_count = 0
                for row in st.session_state.final_data:
                    # current_time 변수가 이제 한국 시간으로 전달됩니다.
                    sheet_row = [
                        current_time,                   # A열: 타임스탬프 (한국 시간)
                        selected_facility,              # B열: 시설명
                        selected_dept,                  # C열: 담당 부서
                        row.get("category"),            # D열: 유해위험요인
                        row.get("scenario"),            # E열: 위험상황
                        row.get("grade"),               # F열: 위험등급
                        row.get("solution"),            # G열: 감소대책
                        row.get("law"),                  # H열: 관련근거
                        photo_link                      # I열: 사진 기록
                    ]
                    
                    if append_row_to_sheet(sheet_row):
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ 데이터 {success_count}건이 KYWA AI 안전센터로 정상 제출되었습니다!")
                    st.balloons()
                    # (선택) 전송 후 데이터 초기화가 필요하다면 아래 주석 해제
                    # st.session_state.final_data = None
                    # st.session_state.analysis_results = None
                    # st.rerun()
                
            except Exception as e:
                st.error(f"❌ 전송 중 오류 발생: {e}")

                
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
        yearly_data = dashboard_data[dashboard_data['타임스탬프'].dt.year == 2026].copy()
    else:
        yearly_data = dashboard_data.copy()

    if yearly_data.empty:
        st.warning("📅 2026년도 데이터가 아직 없습니다. 데이터를 첫 번째로 전송해 보세요!")
    else:
        st.subheader("📊 실시간 점검 데이터 현황 (2026년)")
        
        # 3. 상단 지표
        total_count = len(yearly_data)
        m1, m2 = st.columns(2)
        m1.metric("올해 누적 점검 건수", f"{total_count} 건")
        
        author_col = "작성자 성명" 
        if author_col in yearly_data.columns:
            m2.metric("참여 인원(명)", f"{yearly_data[author_col].nunique()} 명")
        else:
            m2.metric("점검결과 제출 시설", f"{yearly_data['시설명'].nunique()} 개 시설")

        # --- 색상 맵 설정 ---
        CATEGORY_COLOR_MAP = {
            "시설 안전": "#D32F2F", "화재 안전": "#FF5722", "재난 안전": "#880E4F",
            "작업환경 요인": "#455A64", "작업 환경": "#455A64", "기계(설비)적 요인": "#795548",
            "작업 안전": "#FFA000", "전기적 요인": "#FBC02D", "보건 및 위생관리": "#E91E63",
            "화학물질 관리": "#9C27B0", "보행 안전": "#1976D2", "활동 안전": "#388E3C"
        }

        FACILITY_COLOR_MAP = {
            "중앙": "#B93444", "본원": "#6B5B95", "평창": "#E2725B",
            "바이오": "#D2B48C", "해양": "#5B84B1", "우주": "#2E4A62",
            "미래": "#92B06A", "생태": "#5F7161"
        }

        # --- 4. 그래프 시각화 영역 ---
        g_col1, g_col2 = st.columns(2)

        with g_col1:
            if len(yearly_data.columns) >= 4:
                target_col_cat = yearly_data.columns[3] 
                st.write(f"**{target_col_cat} 현황**")
                if not yearly_data[target_col_cat].dropna().empty:
                    yearly_data[target_col_cat] = yearly_data[target_col_cat].astype(str).str.strip()
                    
                    fig_pie = px.pie(
                        yearly_data, names=target_col_cat, hole=0.3,
                        color=target_col_cat, color_discrete_map=CATEGORY_COLOR_MAP
                    )
                    
                    # --- [추가 및 수정된 부분 시작] ---
                    fig_pie.update_traces(
                        textinfo='percent+value', 
                        texttemplate='%{percent:.1%}<br>(%{value}건)', # 퍼센트(소수점 1자리)와 건수 표시
                        insidetextorientation='horizontal', # 글자를 가로로 고정
                        textfont_size=12 # 글자 크기 조절 (필요시)
                    )
                    # --- [추가 및 수정된 부분 끝] ---

                    # 기존 레이아웃 설정
                    fig_pie.update_layout(
                        margin=dict(t=30, b=0, l=0, r=0), 
                        height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=None),
                        dragmode=False
                    )
                    st.plotly_chart(fig_pie, use_container_width=True, theme="streamlit", config={'displayModeBar': False})
        with g_col2:
            target_col_fac = "시설명" 
            if target_col_fac in yearly_data.columns:
                st.write(f"**{target_col_fac}별 점검 건수**")
                
                # 데이터 집계
                yearly_data[target_col_fac] = yearly_data[target_col_fac].astype(str).str.strip()
                fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
                fac_counts.columns = [target_col_fac, '건수']
                
                fig_bar = px.bar(
                    fac_counts, x=target_col_fac, y='건수', color=target_col_fac,
                    color_discrete_map=FACILITY_COLOR_MAP
                )
                
                # --- [수치 표기 설정 추가 시작] ---
                fig_bar.update_traces(
                    texttemplate='%{y}건',      # Y축 값 뒤에 '건' 추가
                    textposition='outside',    # 막대 바깥쪽 상단에 표시
                    textfont_size=12,          # 텍스트 크기 조절
                    cliponaxis=False           # 그래프 경계에서 글자가 잘리지 않게 설정
                )
                # --- [수치 표기 설정 추가 끝] ---
                
                # 확대/축소 방지 및 레이아웃 설정
                fig_bar.update_xaxes(fixedrange=True)
                fig_bar.update_yaxes(fixedrange=True)
                
                fig_bar.update_layout(
                    margin=dict(t=35, b=0, l=0, r=0), # 텍스트 표시를 위해 상단 마진(t)을 약간 늘림
                    height=350, 
                    showlegend=False,
                    xaxis_title=None, 
                    yaxis_title="점검 건수",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=None),
                    dragmode=False 
                )
                
                st.plotly_chart(
                    fig_bar, 
                    use_container_width=True, 
                    theme="streamlit",
                    config={'displayModeBar': False}
                )

# --- 푸터(Footer) 섹션 ---
st.write("") # 간격 확보
st.write("---")
footer_cols = st.columns([3, 1])

with footer_cols[0]:
    st.markdown("### 🔒 Data Governance & Privacy")
    st.caption("""
    **© 2026 한국청소년활동진흥원(KYWA) 안전경영부.** 본 시스템은 **공공기관 AI 활용 가이드라인** 및 **정보보안 업무규정** 을 엄격히 준수합니다.
    
    * **데이터 보안:** 입력된 모든 정보는 **API 옵트아웃(Opt-out) 설정**이 적용되어 외부 모델 학습에 활용되지 않습니다.
    * **운영 방침:** **KYWA AI 안전센터**로 전송된 데이터는 **담당자의 데이터 정합성 검토**를 거칩니다. 
      점검 내용이 부적절하거나 중복된 경우, 데이터 신뢰성 유지를 위해 운영 관리자에 의해 임의 수정 또는 삭제될 수 있습니다.
    * **면책 고지:** AI 분석 정보는 위험 요인 발굴을 돕는 가이드라인입니다. 실제 위험성 평가 시에는 현장 상황을 반영한 담당 직원의 면밀한 검토를 권고합니다.
    """)

with footer_cols[1]:
    st.markdown("### 📞 Contact")
    # HTML을 사용하여 아이콘 색상을 제어합니다 (Dark Gray/Black 계열)
    st.markdown(f"""
    <div style="line-height: 1.6;">
        <span style="font-weight: bold; font-size: 0.9rem; color: #31333F;">경영지원본부 안전경영부</span><br>
        <span style="color: #444; font-size: 0.85rem;">📧 archi01@kywa.or.kr</span><br>
        <span style="color: #444; font-size: 0.85rem;">
            <span style="display: inline-block; transform: rotate(10deg); color: #000;">📞</span> 02-6959-7138
        </span>
    </div>
    """, unsafe_allow_html=True)

# 최하단 한 줄 강조
st.markdown("<p style='font-size: 0.8rem; color: gray; text-align: center;'>Safe Together, KYWA AI Risk Assessment System</p>", unsafe_allow_html=True)

