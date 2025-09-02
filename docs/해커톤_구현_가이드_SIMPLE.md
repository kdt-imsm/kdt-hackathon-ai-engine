# 농촌 일여행 추천 시스템 - 실제 구현 상황

## 🎯 프로젝트 개요

**현재 동작 중인 URL**: http://localhost:8000/public/frontend/app_show_v3/index.html

**AI + 규칙 기반 하이브리드 농촌 일여행 추천 시스템**으로, 사용자 선호도 분석부터 맞춤형 일정 생성까지 지능형 매칭을 제공하는 서비스입니다.

## 🏗️ 실제 아키텍처

### 1. 현재 동작 중인 시스템 구조
```
프론트엔드 (PWA) ↔ FastAPI 백엔드 ↔ CSV 파일 데이터
                              ↑
                      OpenAI GPT-4o-mini (자연어 의도 추출)
```

### 2. 실제 기술 스택
- **프론트엔드**: Vanilla JavaScript (PWA), CSS Grid/Flexbox
- **백엔드**: Python FastAPI
- **데이터 저장소**: CSV/JSON 파일 (PostgreSQL 없음)
- **AI**: OpenAI GPT-4o-mini (자연어 의도 추출만)
- **추천 엔진**: 키워드 매칭 + 스코어링 알고리즘

## 📱 프론트엔드 구현 세부사항

### 1. PWA 앱 구조
- **파일**: `/public/frontend/app_show_v3/index.html`
- **아키텍처**: SPA (Single Page Application)
- **상태 관리**: LocalStorage + 전역 STATE 객체

```javascript
// 핵심 상태 관리
const STATE = {
  view: "onboard",              // 현재 화면
  profile: {},                  // 사용자 프로필
  prefs: {},                   // 선호도 정보
  chosenCards: [],             // 선택한 카드 목록
  last_schedule: null,         // 최신 생성된 일정
  user_id: null               // 백엔드에서 발급받은 사용자 ID
};
```

### 2. 화면 구성 (5단계)
1. **온보딩 (onboard~onboard5)**: 사용자 프로필 + 선호도 수집
2. **홈 (home)**: 캘린더 + 여행 요약 + 자연어 입력
3. **챗봇 (chat)**: 추천 카드 표시 + 일정 생성 + 피드백

### 3. API 통신 구현
```javascript
// config.json 기반 엔드포인트 관리
async function callEngine(pathOrKey, body) {
  const cfg = await loadConfig();
  const ep = resolveEndpoint(pathOrKey, cfg);
  const url = `${cfg.baseURL}${ep}`;
  // ... REST API 호출
}
```

**주요 엔드포인트** (`config.json`):
- `/api/onboarding` - 사용자 프로필 등록
- `/recommendations/with-user` - AI 추천 엔진
- `/api/schedule/with-user` - 일정 생성
- `/api/schedule/feedback` - 일정 수정

## 🤖 실제 구현된 AI 시스템

### 1. 현재 동작하는 AI 파이프라인

#### Stage 1: 자연어 의도 추출 (`app/embeddings/openai_service.py`)
```python
# 자연어 → 구조화된 JSON (GPT-4o-mini)
"내일 김제에서 사과따기 하고 싶어요" 
↓ GPT-4o-mini 의도 추출
{
  "지역": "김제시",
  "활동_유형": ["과수원 체험", "농업 체험"],
  "농업_관심사": ["과일", "사과", "수확체험"],
  "기간": 1,
  "신뢰도": 0.9
}
```

#### Stage 2: 키워드 매칭 + 스코어링 (`app/utils/attraction_scoring.py`)
```python
# 키워드 기반 매칭 + 사용자 선호도 스코어링
def score_and_rank_attractions(attractions, user_travel_styles, user_landscapes):
    # 여행 스타일 매칭 (체험형, 힐링 등)
    # 풍경 선호도 매칭 (산, 바다 등)  
    # 가중치 적용한 점수 계산
    return ranked_attractions
```

#### Stage 3: 규칙 기반 일정 생성 (`app/services/simple_scheduling_service.py`)
```python
# 규칙 기반 + AI 향상 일정 생성
def generate_schedule(natural_request, selected_farm, selected_tours, preferences):
    # 자연어에서 기간/날짜 추출
    # 지리적 최적화 (이동 경로 고려)
    # 운영시간/계절 정보 반영
    return optimized_schedule
```

### 2. 실제 데이터 구조
```python
# 파일 기반 데이터 (Database 없음)
data/
├── dummy_jobs.json              # 농가 일자리 데이터
├── jeonbuk_김제시_attractions.csv  # 지역별 관광지 데이터  
├── jeonbuk_전주시_attractions.csv
└── ... (총 14개 전북 지역)
```

## 🔄 사용자 플로우 구현

### 1. 온보딩 → 프로필 생성
```javascript
// 5단계 온보딩 완료 시
async function sendOnboardingAndGetUserId() {
  const payload = buildOnboardingPayload();
  const data = await callEngine("onboarding", payload);
  STATE.user_id = data.user_id;  // 백엔드에서 user_id 발급
}
```

### 2. 자연어 입력 → AI 추천
```javascript
async function triggerRecommendation(natural_request) {
  // 1) 사용자 메시지 표시
  addMsg(natural_request, true);
  
  // 2) AI 추천 API 호출
  const reco = await engineRecommend(natural_request);
  
  // 3) 농가/관광지 카드 렌더링
  CURRENT_RECO = { jobs: farmCards, tours: tourCards };
  renderCards();
}
```

### 3. 카드 선택 → 일정 생성
```javascript
async function createScheduleWithUser(payload) {
  const sched = await callEngine("plan", {
    user_id: STATE.user_id,
    natural_request: "김제에서 사과따기",
    selected_farm: farm_obj,
    selected_tours: [tour1, tour2]
  });
  
  // 일정 테이블 렌더링
  renderScheduleTable(sched);
}
```

### 4. 피드백 → 일정 수정
```javascript
async function handleScheduleFeedback(feedback) {
  const sched = await sendScheduleFeedback(feedback);
  addMsg("요청하신 내용으로 일정을 수정했어요.");
  renderScheduleTable(sched);
}
```

## 💾 데이터 관리 전략

### 1. 프론트엔드 상태 관리
```javascript
// LocalStorage 기반 영구 저장
function saveState() {
  localStorage.setItem("ims_profile", JSON.stringify(STATE.profile));
  localStorage.setItem("ims_user_id", STATE.user_id);
  localStorage.setItem("ims_last_schedule", JSON.stringify(STATE.last_schedule));
}
```

### 2. 백엔드 벡터 DB
```sql
-- pgvector 확장 활용
CREATE EXTENSION vector;

-- 임베딩 검색 쿼리
SELECT * FROM job_posts 
ORDER BY embedding <-> query_embedding 
LIMIT 10;
```

## 🎨 UI/UX 구현 특징

### 1. 모바일 퍼스트 PWA
- **반응형**: 최대 420px 너비로 모바일 최적화
- **PWA**: Service Worker + Manifest로 앱 형태 제공
- **네이티브 느낌**: iOS/안드로이드 디자인 패턴 적용

### 2. 직관적 카드 인터페이스
```css
.cardItem {
  border-radius: 18px;
  box-shadow: 0 6px 18px rgba(0,0,0,.04);
  transition: all 0.2s ease;
}

.cardItem.active {
  border: 2px solid var(--primary);
  transform: translateY(-2px);
}
```

### 3. 실시간 피드백 시스템
- **로딩 애니메이션**: 3단계 도트 애니메이션으로 AI 처리 과정 시각화
- **단계별 안내**: "분석 중... → 추천 생성 중... → 일정 최적화 중..."

## 🚀 실제 성능 최적화 

### 1. API 호출 최적화
- **타임아웃**: 20초 제한으로 UX 보장
- **에러 핸들링**: HTTP 상태별 맞춤 에러 메시지
- **이미지 최적화**: 한국관광공사 API 이미지 사전 필터링

### 2. 데이터 처리 최적화
- **CSV 캐싱**: 지역별 관광지 데이터 메모리 캐싱
- **스코어링 알고리즘**: 키워드 매칭 후 점수 계산으로 성능 향상
- **이미지 병렬 처리**: 관광지 이미지 동시 확인

## 🔧 실제 핵심 구현 포인트

### 1. GPT-4o-mini 자연어 의도 추출
```python
# 한국어 자연어 처리 프롬프트 최적화 (실제 구현)
system_prompt = """
당신은 전북 농촌 관광 전문 자연어 분석 AI입니다.
사용자의 자연어 요청에서 여행 의도를 정확하게 추출해야 합니다.

## 전북 지역 정보 (정확한 매핑 필수)
- 시: 전주시, 군산시, 익산시, 정읍시, 남원시, 김제시
- 군: 완주군, 진안군, 무주군, 장수군, 임실군, 순창군, 고창군, 부안군

## 추출 정보
1. **지역**: 위 목록에서 정확한 행정구역명으로 매핑
2. **시기**: 구체적인 월/계절 정보
3. **기간**: 일수 정확 추출 (한글 숫자 포함: 하루, 이틀, 열흘 등)
4. **활동_유형**: 구체적인 체험 활동
"""
```

### 2. 키워드 매칭 + 스코어링 시스템 (실제 구현)
```python
# 스코어링 기반 추천 (벡터 검색 대신)
def score_and_rank_attractions(attractions, user_travel_styles, user_landscapes):
    scored = []
    for attraction in attractions:
        score = 0
        
        # 여행 스타일 매칭 (높은 가중치)
        attr_styles = parse_keywords(attraction.get('travel_style_keywords', ''))
        matches = sum(1 for style in user_travel_styles 
                     if any(keywords_match(style, attr_style) for attr_style in attr_styles))
        score += matches * 2
        
        # 풍경 선호도 매칭 (보너스)
        if user_landscapes:
            attr_landscapes = parse_keywords(attraction.get('landscape_keywords', ''))
            landscape_match = any(keywords_match(landscape, attr_land) 
                                for landscape in user_landscapes 
                                for attr_land in attr_landscapes)
            if landscape_match:
                score += 1
        
        scored.append(AttractionScore(..., score=score))
    
    return sorted(scored, key=lambda x: x.score, reverse=True)
```

### 3. 규칙 기반 스마트 스케줄링 (실제 구현)
```python
# 규칙 기반 지능형 일정 생성 (GPT Agent 대신)
class SimpleSchedulingService:
    def generate_schedule(self, natural_request, selected_farm, selected_tours, preferences):
        # 1) 자연어에서 기간 추출 (한글 숫자 지원)
        duration = self._extract_duration_from_request(natural_request)
        
        # 2) 시작 날짜 추출 및 특별 이벤트 고려
        start_date = self._extract_start_date_from_request(natural_request, region)
        # 김제 지역 + 10월 = 김제지평선축제 자동 포함
        
        # 3) 지리적 최적화 (이동 경로 고려)
        optimized_schedule = self._optimize_travel_route(farm, tours, duration)
        
        return optimized_schedule
```

## 📊 실제 구현 완성도와 기술적 어필 포인트

### 1. ✅ 실제 구현된 기술적 혁신성
- **GPT-4o-mini 자연어 처리**: 한국어 여행 의도를 JSON으로 정확 추출
- **지능형 스코어링**: 키워드 매칭 + 가중치 기반 개인화 추천
- **하이브리드 추천**: AI 의도 추출 + 규칙 기반 매칭의 조합

### 2. ✅ 완성된 사용자 경험
- **5단계 온보딩**: 사용자 선호도 체계적 수집 (완료)
- **자연어 인터페이스**: "10월에 김제에서 열흘간 과수원 체험" → 즉시 추천 (완료)
- **실시간 피드백**: "첫째날 일정을 다른 관광지로 바꿔줘" → 일정 수정 (완료)

### 3. ✅ 실용적 확장 가능성
- **모듈화 설계**: 의도 추출 → 스코어링 → 스케줄링 독립 모듈 (완료)
- **API 우선**: RESTful API로 프론트엔드 완전 분리 (완료)
- **고도화 준비**: advanced_features에 벡터 DB, 복잡한 AI 시스템 준비

### 4. ⚠️ 고도화 여지 (향후 개선 가능)
- **벡터 검색**: PostgreSQL + pgvector (advanced_features에 구현 완료, 미적용)
- **복합 AI Agent**: GPT-4o 기반 스마트 스케줄링 (advanced_features에 준비)
- **실시간 DB**: 현재는 CSV 파일, DB 연동으로 확장 가능

---

## 🎯 멘토님께 강조할 핵심 메시지

**"단순해 보이지만 실용적이고 완성도 높은 AI 추천 시스템"**

1. **실제 동작하는 완전한 시스템**: 온보딩부터 일정 확정까지 전 과정 완료
2. **AI + 규칙의 효과적 조합**: 과도한 AI 의존 대신 정확하고 빠른 하이브리드 방식
3. **해커톤 완성도**: 3일 내에 실제 사용 가능한 서비스 레벨로 구현
4. **확장 설계**: 고도화 기능들이 이미 준비되어 단계적 업그레이드 가능

**기술적 어필 포인트:**
- GPT-4o-mini 기반 한국어 자연어 처리의 정확성
- 키워드 매칭 + 스코어링의 빠른 응답성
- PWA 기반 모바일 최적화 UX
- 전북 14개 시군 전지역 실제 데이터 활용