# 농촌 일자리·관광 통합 추천 시스템 API 명세서 (JavaScript 연동용)

## 엔드포인트 요약

| HTTP Method | 엔드포인트 | 설명 | 주요 응답 데이터 |
|-------------|-----------|------|----------------|
| POST | `/api/onboarding` | 사용자 온보딩 및 선호도 설정 | user_id, user_data |
| POST | `/recommendations/with-user` | 자연어 입력으로 추천 카드 조회 | farms (5개), tour_spots (5개) |
| POST | `/api/schedule/with-user` | 선택된 카드로 일정 생성 | itinerary, bubble_schedule |
| POST | `/api/schedule/feedback` | 일정 피드백 및 수정 | updated_schedule |
| POST | `/api/schedule/{itinerary_id}/summary` | AI 여행 요약 생성 | travel_summary |

## API 사용 플로우

### 1. 온보딩 (사용자 선호도 설정)

**POST** `/api/onboarding`

사용자의 기본 정보와 선호도를 등록하고 개인화된 추천을 위한 user_id를 발급합니다.

**Request Body:**
```json
{
  "real_name": "김지현",
  "name": "지현이", 
  "age": "24",
  "gender": "여",
  "sido": "서울특별시",
  "sigungu": "강남구",
  "with_whom": "친구와",
  "selected_views": ["산", "숲"],
  "selected_styles": ["체험형", "힐링·여유"], 
  "selected_jobs": ["과수", "채소"],
  "additional_requests": ["뚜벅이 여행", "자연 산책", "시장투어", "숨겨진 맛집", "빵 투어"]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "온보딩이 완료되었습니다.",
  "user_id": "user_1693498765",
  "user_data": {
    "address": "서울특별시 강남구",
    "age": "24",
    "gender": "여",
    "name": "지현이",
    "pref_etc": ["뚜벅이 여행", "자연 산책", "시장투어", "숨겨진 맛집", "빵 투어"],
    "pref_jobs": ["과수", "채소"],
    "pref_style": ["체험형", "힐링·여유"],
    "pref_view": ["산", "숲"],
    "real_name": "김지현",
    "with_whom": "친구와"
  }
}
```

### 2. 추천 카드 조회 (자연어 입력)

**POST** `/recommendations/with-user`

사용자의 자연어 입력과 선호도를 분석하여 농가 5개와 관광지 5개를 추천합니다.

**Request Body:**
```json
{
  "user_id": "user_1693498765",
  "natural_request": "10월에 열흘간 김제에서 과수원 체험하고 싶어"
}
```

**Response:**
```json
{
  "status": "success", 
  "data": {
    "farms": [
      {
        "farm_id": "farm_0",
        "farm": "김제 과수농장",
        "title": "사과 수확 체험", 
        "address": "전북 김제시 금구면",
        "start_time": "08:00",
        "end_time": "17:00", 
        "photo": "/public/images/jobs/김제_사과.jpg",
        "required_people": "2-4명"
      }
    ],
    "tour_spots": [
      {
        "tour_id": "574285",
        "name": "김제지평선축제",
        "address": "전북 김제시 부량면", 
        "photo": "http://tong.visitkorea.or.kr/cms/resource/47/3516347_image2_1.jpg"
      }
    ],
    "target_region": "김제시",
    "bubble_data": {
      "total_farms": 5,
      "total_tours": 5,
      "estimated_duration": 10,
      "season_info": "10월 초"
    },
    "scored_attractions": [
      {
        "name": "김제지평선축제",
        "contentid": "574285",
        "landscape_keywords": "강·호수",
        "travel_style_keywords": "축제·이벤트;문화·역사;체험형",
        "_score": 20
      }
    ]
  },
  "user_info": {
    "user_id": "user_1693498765",
    "name": "지현이",
    "with_whom": "친구와",
    "address": "서울특별시 강남구"
  }
}
```

### 3. 일정 생성

**POST** `/api/schedule/with-user`

사용자가 선택한 농가와 관광지를 바탕으로 최적화된 다일간 농촌 일여행 일정을 생성합니다.

**Request Body:**
```json
{
  "user_id": "user_1693498765",
  "natural_request": "10월에 열흘간 김제에서 과수원 체험하고 싶어",
  "selected_farm": {
    "farm_id": "farm_0",
    "farm": "김제 과수농장", 
    "title": "사과 수확 체험",
    "address": "전북 김제시 금구면"
  },
  "selected_tours": [
    {
      "tour_id": "12345",
      "name": "김제지평선축제",
      "address": "전북 김제시 부량면"
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "itinerary_id": "schedule_20250831_143000",
    "total_days": 10,
    "itinerary": [
      {
        "day": 1,
        "date": "10월 1일 (화)",
        "schedule_type": "관광지", 
        "name": "벽골제",
        "start_time": "15:00",
        "address": "전북 김제시"
      },
      {
        "day": 2,
        "date": "10월 2일 (수)",
        "schedule_type": "농가", 
        "name": "김제 과수농장",
        "start_time": "08:00",
        "address": "전북 김제시 금구면"
      }
    ],
    "bubble_schedule": {
      "grouped_schedule": [
        {
          "order": 1,
          "type": "tour",
          "title": "Day 1: 도착 및 관광",
          "subtitle": "벽골제",
          "date": "10월 1일 (화)",
          "start_time": "15:00",
          "description": "10월 1일 (화) 15:00"
        },
        {
          "order": 2, 
          "type": "farm_period",
          "title": "Day 2-8: 농가 체험",
          "subtitle": "김제 과수농장",
          "description": "7일간 농가 일정 (08:00-17:00)"
        }
      ],
      "calendar_events": [
        {
          "date": "10/01/2025 9:00 am",
          "activity": "벽골제",
          "day": 1,
          "type": "관광지"
        },
        {
          "date": "10/02/2025 9:00 am",
          "activity": "김제 과수농장",
          "day": 2,
          "type": "농가"
        }
      ]
    },
    "summary": {
      "duration": 10,
      "farm_days_count": 7,
      "tour_days_count": 3,
      "region": "김제시"
    }
  },
  "user_info": {
    "user_id": "user_1693498765",
    "name": "지현이",
    "with_whom": "친구와",
    "address": "서울특별시 강남구"
  }
}
```

### 4. 일정 피드백 및 수정

**POST** `/api/schedule/feedback`

생성된 일정에 대해 자연어 피드백을 제공하여 실시간으로 일정을 수정합니다.

**Request Body:**
```json
{
  "user_id": "user_1693498765",
  "feedback": "첫째날 일정을 바꿔주세요"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "itinerary_id": "schedule_20250831_143000",
    "total_days": 10,
    "itinerary": [
      {
        "day": 1,
        "date": "10월 1일 (화)",
        "schedule_type": "관광지", 
        "name": "김제지평선축제",
        "start_time": "14:00",
        "address": "전북 김제시 부량면"
      },
      {
        "day": 2,
        "date": "10월 2일 (수)",
        "schedule_type": "농가", 
        "name": "김제 과수농장",
        "start_time": "08:00",
        "address": "전북 김제시 금구면"
      }
    ],
    "bubble_schedule": {
      "grouped_schedule": [
        {
          "order": 1,
          "type": "tour",
          "title": "Day 1: 도착 및 관광",
          "subtitle": "김제지평선축제",
          "date": "10월 1일 (화)",
          "start_time": "14:00",
          "description": "10월 1일 (화) 14:00"
        },
        {
          "order": 2, 
          "type": "farm_period",
          "title": "Day 2-8: 농가 체험",
          "subtitle": "김제 과수농장",
          "description": "7일간 농가 일정 (08:00-17:00)"
        }
      ]
    },
    "summary": {
      "duration": 10,
      "farm_days_count": 7,
      "tour_days_count": 3,
      "region": "김제시"
    }
  },
  "message": "피드백에 따라 일정이 수정되었습니다."
}
```

## 응답 코드

| 상태 코드 | 설명 |
|----------|------|
| 200 | 요청 성공 |
| 201 | 리소스 생성 성공 |
| 400 | 잘못된 요청 데이터 |
| 404 | 요청한 리소스를 찾을 수 없음 |
| 500 | 서버 내부 오류 |

## 에러 응답 형식

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "사용자 입력이 유효하지 않습니다",
    "details": "user_input 필드는 필수입니다"
  }
}
```

### 5. AI 여행 요약 생성

**POST** `/api/schedule/{itinerary_id}/summary`

확정된 일정에 대해 AI가 생성한 매력적인 여행 요약을 제공합니다.

**Request Body:** 없음 (itinerary_id는 URL 경로에 포함)

**Response:**
```json
{
  "status": "success",
  "data": {
    "travel_summary": "🍎 김제에서의 달콤한 10일간 농촌 체험 여행!\n\n첫날에는 아름다운 벽골제에서 가을의 정취를 만끽하며 여행을 시작합니다. 🌾 이후 7일간은 김제 과수농장에서 신선한 사과를 직접 수확하며 농촌의 진정한 매력을 체험하게 됩니다.\n\n매일 아침 8시부터 오후 5시까지 농장에서 보내는 시간은 도시에서는 느낄 수 없는 소중한 경험이 될 것입니다. 🍃 친구와 함께하는 이번 여행은 자연 속에서의 힐링과 체험의 완벽한 조화를 선사할 거예요!"
  }
}
```

## JavaScript 연동 예시

### 기본 설정
```javascript
const BASE_URL = 'http://localhost:8000'; // 또는 ngrok URL

// 공통 fetch 함수
async function apiCall(endpoint, data) {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
  });
  return await response.json();
}
```

### 1. 온보딩
```javascript
const onboardingData = {
  real_name: "김지현",
  name: "지현이",
  age: "24",
  gender: "여",
  sido: "서울특별시",
  sigungu: "강남구", 
  with_whom: "친구와",
  selected_views: ["산", "숲"],
  selected_styles: ["체험형", "힐링·여유"],
  selected_jobs: ["과수", "채소"],
  additional_requests: ["뚜벅이 여행", "자연 산책", "시장투어", "숨겨진 맛집", "빵 투어"]
};

const onboardingResult = await apiCall('/api/onboarding', onboardingData);
const userId = onboardingResult.user_id;
```

### 2. 추천 받기
```javascript
const recommendationData = {
  user_id: userId,
  natural_request: "10월에 열흘간 김제에서 과수원 체험하고 싶어"
};

const recommendations = await apiCall('/recommendations/with-user', recommendationData);
const farms = recommendations.data.farms;
const tourSpots = recommendations.data.tour_spots;
```

### 3. 일정 생성
```javascript
const scheduleData = {
  user_id: userId,
  natural_request: "10월에 열흘간 김제에서 과수원 체험하고 싶어",
  selected_farm: farms[0], // 첫 번째 농가 선택
  selected_tours: [tourSpots[0], tourSpots[1]] // 첫 두 관광지 선택
};

const schedule = await apiCall('/api/schedule/with-user', scheduleData);
const itinerary = schedule.data.itinerary;
const bubbleSchedule = schedule.data.bubble_schedule;
```

### 4. 피드백
```javascript
const feedbackData = {
  user_id: userId,
  feedback: "첫째날 일정을 바꿔주세요"
};

const updatedSchedule = await apiCall('/api/schedule/feedback', feedbackData);
```

### 5. AI 여행 요약 생성
```javascript
// 일정 ID는 3단계에서 받은 schedule.data.itinerary_id 사용
const itineraryId = schedule.data.itinerary_id;

const summaryResponse = await fetch(`${BASE_URL}/api/schedule/${itineraryId}/summary`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  }
});

const summaryResult = await summaryResponse.json();
const travelSummary = summaryResult.data.travel_summary;

console.log('AI 생성 여행 요약:', travelSummary);
```

## 주요 특징

- **AI 기반 자연어 처리**: GPT-4o-mini로 한국어 자연어를 구조화된 데이터로 변환
- **개인화된 추천**: 사용자 선호도 기반 스코어링 시스템 (landscape_keywords, travel_style_keywords)
- **스마트 스케줄링**: 지리적 위치와 시간 최적화를 고려한 다일간 농촌 일정 생성
- **실시간 피드백**: 자연어 피드백에 따른 즉시 일정 수정
- **통합 데이터**: 농가 일자리와 관광지를 결합한 맞춤형 농촌 일여행 추천

## 선호도 옵션 목록

온보딩 단계에서 사용자가 선택할 수 있는 옵션들입니다.

### 풍경 선호도 (selected_views) - 복수 선택 가능
- `"산"`, `"바다"`, `"강·호수"`, `"숲"`, `"섬"`, `"들판"`

### 여행 스타일 (selected_styles) - 복수 선택 가능
- `"힐링·여유"`, `"체험형"`, `"야외활동"`, `"레저·액티비티"`
- `"문화·역사"`, `"축제·이벤트"`, `"먹거리 탐방"`, `"사진 스팟"`

### 체험 유형 (selected_jobs) - 복수 선택 가능
- `"채소"`, `"과수"`, `"화훼"`, `"식량작물"`, `"축산"`, `"농기계"`

### 함께 가는 사람 (with_whom) - 단일 선택
- `"혼자"`, `"친구와"`, `"가족과"`, `"연인과"`

## 지원 지역 목록

전북 지역 14개 시군:
- 시: `"전주시"`, `"군산시"`, `"익산시"`, `"정읍시"`, `"남원시"`, `"김제시"`
- 군: `"완주군"`, `"진안군"`, `"무주군"`, `"장수군"`, `"임실군"`, `"순창군"`, `"고창군"`, `"부안군"`

## 서비스 특징 (참고용)

다음은 백엔드에서 자동으로 처리되는 사항들입니다. 프론트엔드에서는 별도 구현이 필요하지 않습니다.

### 자동 처리되는 사항들
- **김제지평선축제 우선 배치**: 김제시 요청 시 자동으로 첫 번째 카드로 제공
- **스마트 스코어링**: 사용자 선호도 기반 관광지 자동 순위 정렬
- **최적 일정 생성**: 지리적 위치와 시간을 고려한 자동 일정 배치
- **복수 landscape 지원**: 사용자가 여러 풍경을 선택해도 자동으로 매칭

### 제약사항
- 일정은 최대 10일까지만 가능
- 농가는 1개만 선택 가능 (관광지는 복수 선택 가능)
- 자연어 요청에 지역명이 포함되어야 함 (예: "김제에서", "전주에서")

## 데이터 소스

- **농가 일자리**: CSV 기반 전북 지역 농가 데이터 (더미)
- **관광지 정보**: 한국관광공사 API 연동 + CSV 데이터
- **사용자 선호도**: 온보딩 단계에서 수집된 키워드 배열
- **스코어링**: attraction_scoring.py의 preference-based 알고리즘