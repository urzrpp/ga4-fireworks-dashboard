"""
GA4 연동 설정 파일

1. 아래 GA4_PROPERTY_ID 를 본인 속성 ID로 교체하세요. (숫자만, 'properties/' 접두어 제외)
   - GA4 관리 > 속성 설정에서 확인 가능 (예: 313XXXXXXX)
2. 서비스 계정 JSON 키 파일을 이 폴더에 넣고 파일명을 아래 CREDENTIALS_FILE 에 맞춰주세요.
   (또는 환경변수 GOOGLE_APPLICATION_CREDENTIALS 로 경로를 지정해도 됩니다)
"""

import os

# GA4 속성 ID (필수 - 본인 값으로 교체)
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "550311577")

# 서비스 계정 키 파일 경로
CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "service-account-key.json"),
)

# 분석 기간 (기본: 최근 28일)
DATE_RANGE_START = os.environ.get("GA4_DATE_START", "28daysAgo")
DATE_RANGE_END = os.environ.get("GA4_DATE_END", "today")

# 퍼널 분석 단계 정의.
# type "event" = eventName 기준, type "page" = pagePath 기준(페이지 접속).
# 실제 GA4 pagePath 데이터로 검증한 순서(활성 사용자 수 단조 감소 확인됨):
# 진입 -> 키워드 이벤트 페이지 접속 -> 키워드 참여 -> 본인인증 제출 -> 이벤트 완료
FUNNEL_STEPS = [
    {"type": "event", "name": "session_start", "label": "캠페인 진입"},
    {"type": "page", "path": "/event/keyword", "label": "키워드 이벤트 페이지 접속"},
    {"type": "event", "name": "keyword_submit", "label": "키워드 참여"},
    {"type": "event", "name": "auth_form_submit", "label": "본인인증 제출"},
    {"type": "event", "name": "fireworks_event_complete", "label": "이벤트 완료"},
]

# 프로모션/캠페인으로 간주할 이름 필터 (선택) - None이면 전체 캠페인 표시
# 예: "promo" 또는 "sale" 이 캠페인명에 포함된 것만 보고 싶다면 문자열 지정
PROMO_NAME_FILTER = os.environ.get("GA4_PROMO_FILTER", None)

# 이벤트(프로모션) 기간 및 목표
CAMPAIGN_START = os.environ.get("GA4_CAMPAIGN_START", "2026-08-19")
CAMPAIGN_END = os.environ.get("GA4_CAMPAIGN_END", "2026-08-28")
TARGET_ACTIVE_USERS = int(os.environ.get("GA4_TARGET_ACTIVE_USERS", "500000"))

# 인증 전환율 계산에 쓰는 시작 이벤트 / 인증 이벤트
FUNNEL_ENTRY_EVENT = "session_start"
AUTH_EVENT = "auth_form_submit"

# "완료"로 볼 이벤트들 (이름에 complete가 들어간 이벤트를 자동 탐지해 사용하되,
# 명시적으로 지정하고 싶으면 여기에 직접 채워도 됨. None이면 자동 탐지)
COMPLETE_EVENTS = None
