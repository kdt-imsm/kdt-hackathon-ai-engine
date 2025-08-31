# 프로젝트 폴더 활용 가이드

## **프로젝트 개요**

**농촌 일자리·관광 통합 추천 시스템** - KDT 해커톤 프로젝트

- 사용자 선호도 기반 농가 일자리 + 관광지 추천
- AI 기반 맞춤형 일정 생성
- Bubble 노코드 플랫폼과 연동 가능

---

## **프로젝트 버전 구조**

### **현재 사용 버전 (app/)**

**목적**: 해커톤 시연용 - 로컬서버 + Bubble 연동

**특징:**

- 단순하고 안정적인 구조
- 로컬 서버에서 Bubble과 직접 연동
- 빠른 개발 및 테스트 가능
- 실시간 디버깅 용이
- **최소한의 의존성**으로 에러 최소화

**주요 기능:**

- 자연어 기반 추천 요청 처리
- 지역별 농가/관광지 데이터 매칭
- 선호도 키워드 기반 추천
- AI 기반 일정 생성
- 피드백 처리 및 일정 수정

### **고도화 버전 (advanced_features/)**

**목적**: 향후 발전 및 상용화용 - 복합 AI Agent 시스템

**특징:**

- GPT-4o 기반 다중 AI Agent
- 벡터 데이터베이스 (pgvector) 활용
- 복잡한 개인화 추천 엔진
- 실시간 피드백 학습
- **완전한 의존성**으로 모든 고급 기능 지원

**주요 기능:**

- 벡터 임베딩 기반 의미 검색
- Smart Scheduling Orchestrator
- Intelligent Planner Agent
- 사용자 행동 패턴 학습

---

## 📁 **폴더 구조**

```
kdt_ai_part/
├── 📂 app/                          # 🎯 현재 사용 버전
│   ├── main.py                     # FastAPI 메인 애플리케이션
│   ├── config.py                   # 환경 설정
│   ├── services/                   # 비즈니스 로직
│   │   ├── simple_recommendation_service.py
│   │   ├── simple_scheduling_service.py
│   │   └── detail_loader.py
│   ├── embeddings/                 # OpenAI 서비스
│   │   └── openai_service.py
│   └── utils/                      # 유틸리티
│       └── jeonbuk_region_mapping.py
│
├── 📂 advanced_features/            # 🚀 고도화 버전
│   ├── main_old.py                 # 복잡한 AI Agent 시스템
│   ├── db/                         # 데이터베이스 모델 (PostgreSQL)
│   ├── nlp/                        # 자연어 처리
│   ├── scripts/                    # 데이터 처리 스크립트
│   └── utils/                      # 고급 유틸리티
│
├── 📂 data/                         # 데이터
│   ├── dummy_jobs.json             # 농가 데이터
│   └── jeonbuk_{지역}_*.csv         # 지역별 관광/숙박/음식점 데이터
│
├── 📂 public/                       # 정적 파일 (테스트 UI)
│   └── index.html                  # 테스트용 웹 인터페이스
│
├── 📂 docs/                         # 문서 파일
│   └── PROJECT_GUIDE.md             # 이 문서
│
├── requirements.txt                # 현재 버전용 최소 의존성
├── requirements-advanced.txt       # 고도화 버전용 전체 의존성
├── vercel.json                     # Vercel 배포 설정 (현재 버전용)
├── CLAUDE.md                       # 개발 가이드
└── 로컬서버_BUBBLE_연동가이드.md   # Bubble 연동 완전 가이드
```

---

## **실행 방법**

### **Step 1: 환경 설정**

```bash
# 가상환경 생성 및 활성화 (이미 있으면 생략)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### **Step 2: 의존성 설치**

#### **현재 사용 버전 (app/) - 권장**

```bash
# 최소 필수 의존성만 설치 (에러 최소화)
pip install -r requirements.txt
```

#### **고도화 버전 (advanced_features/) - 전체 기능 필요시**

```bash
# 전체 의존성 설치 (PostgreSQL, 벡터DB 등 포함)
pip install -r requirements-advanced.txt
```

### **Step 3: 환경변수 설정**

```bash
# .env 파일 생성 및 설정
cp .env.example .env  # 또는 직접 생성
```

`.env` 파일 내용:

```env
# OpenAI API (필수 - 일정 생성용)
OPENAI_API_KEY=your_openai_api_key_here

# 한국관광공사 API (선택사항)
TOUR_API_KEY=your_tour_api_key_here

# 기타 설정
EMBED_MODEL=text-embedding-3-small
SLOT_MODEL=gpt-4o-mini
ITINERARY_MODEL=gpt-4o-mini
CACHE_TTL=300
```

### **Step 4: 서버 실행**

#### **현재 버전 (app/) 실행**

```bash
# Bubble 연동 가능한 방식으로 실행 (중요!)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### **고도화 버전 (advanced_features/) 실행**

```bash
# PostgreSQL 서버 먼저 시작 필요
# 복잡한 AI Agent 시스템 실행
python advanced_features/main_old.py
```

### **Step 5: 동작 확인**

```bash
# 헬스 체크
curl http://localhost:8000/healthz

# 브라우저에서 확인
http://localhost:8000/docs        # API 문서 (Swagger)
http://localhost:8000/public/     # 테스트 UI
```

---

## **Bubble 연동 방법**

### **핵심 3단계**

1. **IP 확인**: `ifconfig | grep "inet " | grep -v "127.0.0.1"`
2. **Bubble API URL**: `http://[확인된IP]:8000/recommendations`
3. **연결 테스트**: "Initialize call"로 200 OK 확인

### **주요 API 엔드포인트**

- `POST /recommendations` - 추천 받기
- `POST /api/schedule` - 일정 생성
- `POST /api/schedule/feedback` - 피드백 처리

**자세한 연동 방법**: `로컬서버_BUBBLE_연동가이드.md` 참고

---

## **의존성 파일 사용 가이드**

### **requirements.txt (현재 버전용)**

**사용 시기**:

- 해커톤, 시연, 빠른 프로토타이핑
- Bubble과 연동하여 기본 기능만 필요한 경우
- 에러 최소화가 중요한 경우

**포함 내용**:

- FastAPI, uvicorn (웹 서버)
- OpenAI (AI 일정 생성)
- httpx (관광공사 API 호출)
- 기본 설정 라이브러리들

```bash
pip install -r requirements.txt
```

### **requirements-advanced.txt (고도화 버전용)**

**사용 시기**:

- 본격적인 개발 및 상용화
- 벡터 검색, AI Agent 등 고급 기능 필요
- PostgreSQL 데이터베이스 사용
- 완전한 개발 환경 구축

**추가 포함 내용**:

- PostgreSQL, pgvector (벡터 데이터베이스)
- pandas, numpy (데이터 처리)
- sentence-transformers (임베딩)
- Redis (캐싱)
- pytest (테스팅)
- 개발 도구들 (black, flake8 등)

```bash
pip install -r requirements-advanced.txt
```

### **어떤 것을 선택할까?**

| 상황            | 추천 파일                   | 이유                   |
| --------------- | --------------------------- | ---------------------- |
| **해커톤 시연** | `requirements.txt`          | 빠른 설치, 에러 최소화 |
| **Bubble 연동** | `requirements.txt`          | 필수 기능만으로 충분   |
| **로컬 개발**   | `requirements.txt`          | 가벼운 환경으로 개발   |
| **상용화 준비** | `requirements-advanced.txt` | 모든 기능 필요         |
| **AI 고도화**   | `requirements-advanced.txt` | 벡터DB, 고급 AI 기능   |
| **팀 개발**     | `requirements-advanced.txt` | 완전한 개발 도구       |

---

## **개발 워크플로우**

### **팀 개발 시 권장 사항**

1. **브랜치 전략**

   - `main`: 안정 버전 (현재 app/ 버전)
   - `feature/*`: 새 기능 개발
   - `advanced/*`: 고도화 버전 개발

2. **개발 환경**

   - 각자 로컬에서 개발 및 테스트
   - Bubble 연동 시 IP 주소 공유
   - 공통 데이터셋 사용

3. **의존성 관리**
   - 기본 개발: `requirements.txt`
   - 고급 기능 개발 시: `requirements-advanced.txt`
   - 새 의존성 추가 시 두 파일 모두 업데이트

---

## **데이터 구조**

### **주요 데이터 파일**

- `dummy_jobs.json`: 농가 일자리 데이터 (23KB, 140개)
- `jeonbuk_{지역}_attractions.csv`: 지역별 관광지 (14개 지역)
- `jeonbuk_{지역}_accommodations.csv`: 지역별 숙박시설
- `jeonbuk_{지역}_restaurants.csv`: 지역별 음식점

### **API 응답 형식**

```json
{
  "status": "success",
  "data": {
    "farms": [
      {
        "farm_id": "farm_0",
        "farm": "농장명",
        "title": "작업 내용",
        "address": "전북 김제시...",
        "start_time": "08:00",
        "end_time": "16:00",
        "photo": "/public/images/jobs/image.jpg"
      }
    ],
    "tour_spots": [
      {
        "tour_id": "12345",
        "name": "관광지명",
        "address": "전북 김제시...",
        "photo": "https://image-url.jpg"
      }
    ]
  }
}
```

---

## **트러블슈팅**

### **자주 발생하는 문제들**

1. **"Address already in use" 에러**

   ```bash
   pkill -f uvicorn
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **의존성 충돌 에러**

   ```bash
   # 현재 버전 재설치
   pip uninstall -r requirements-advanced.txt -y
   pip install -r requirements.txt
   ```

3. **Bubble 연동 실패**

   - 로컬 서버 실행 상태 확인
   - IP 주소 변경 여부 확인
   - 같은 WiFi 네트워크 연결 확인

4. **OpenAI API 에러**

   - `.env` 파일의 `OPENAI_API_KEY` 확인
   - API 키 유효성 및 잔액 확인

5. **PostgreSQL 관련 에러 (고도화 버전)**
   - PostgreSQL 서버 실행 상태 확인
   - pgvector 확장 설치 여부 확인

## **테스트 방법**

1. **현재 버전 테스트**

   - 로컬에서 API 테스트 (Postman, curl)
   - 브라우저에서 테스트 UI 확인
   - Bubble과 연동 테스트

2. **고도화 버전 테스트**
   - PostgreSQL 연결 확인
   - 벡터 검색 기능 테스트
   - AI Agent 동작 확인

---

## ✅ **체크리스트**

### **개발 시작 전**

- [ ] 저장소 클론 및 환경 설정 완료
- [ ] **적절한 requirements 파일 선택**
  - [ ] 기본 개발: `pip install -r requirements.txt`
  - [ ] 고급 기능: `pip install -r requirements-advanced.txt`
- [ ] 가상환경 활성화 확인
- [ ] `.env` 파일 설정 (OpenAI API 키)
- [ ] 로컬 서버 실행 및 동작 확인

### **Bubble 연동 시**

- [ ] `--host 0.0.0.0` 옵션으로 서버 실행
- [ ] IP 주소 확인 및 Bubble API URL 설정
- [ ] API 연결 테스트 (Initialize call)
- [ ] 실제 데이터로 워크플로우 테스트

### **배포 전**

- [ ] 선택한 버전에 맞는 requirements 파일로 테스트
- [ ] 모든 기능 정상 동작 확인
- [ ] 에러 처리 및 예외 상황 테스트
- [ ] 팀원 간 크로스 테스트 완료

---

## **마무리**

이 프로젝트는 **두 가지 버전과 의존성 구조**로 구성되어 있습니다:

### **빠른 시작 (권장)**

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### **완전한 개발 환경**

```bash
pip install -r requirements-advanced.txt
# PostgreSQL 서버 시작 후
python advanced_features/main_old.py
```
