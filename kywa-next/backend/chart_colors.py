"""Stable KYWA colors shared by report and web charts."""
CATEGORY_COLOR_MAP = {
    '시설 안전':'#D32F2F','화재 안전':'#FF5722','재난 안전':'#880E4F',
    '작업 안전':'#FFA000','작업 특성':'#E64A19','기계(설비)적 요인':'#795548',
    '전기적 요인':'#FBC02D','보건 및 위생관리':'#E91E63','화학물질 관리':'#9C27B0',
    '작업 환경':'#455A64','보행 안전':'#1976D2','활동 안전':'#388E3C'}
FACILITY_COLOR_MAP = {'중앙':'#B93444','본원':'#6B5B95','평창':'#E2725B','바이오':'#D2B48C',
    '해양':'#5B84B1','우주':'#2E4A62','미래':'#92B06A','생태':'#5F7161'}
FALLBACK_COLOR = '#757575'


FACILITY_PALETTE = ['#5B84B1','#6B5B95','#5F7161','#B93444','#E2725B','#2E4A62','#92B06A','#967B57','#507C85','#937078','#657D4E','#81738F']
def facility_color(org, facility):
    if org.id == 'kywa': return FACILITY_COLOR_MAP.get(facility,FALLBACK_COLOR)
    return FACILITY_PALETTE[org.facilities.index(facility)%len(FACILITY_PALETTE)] if facility in org.facilities else FALLBACK_COLOR
