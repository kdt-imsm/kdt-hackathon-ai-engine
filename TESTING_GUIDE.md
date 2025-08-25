# 일멍쉬멍 - 농촌 일자리·관광 추천 시스템 테스트 가이드

이 문서는 AI 기반 농촌 일여행 추천 시스템을의 **간단한 테스트 가이드**입니다.

## 테스트 단계

### 1단계: 환경 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음을 입력하세요.

```bash
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_URI=postgresql://username:password@localhost:5432/database_name
```

### 2단계: 설치 및 초기화

터미널에서 다음 명령어들을 순서대로 실행하세요.

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 필요하다면
# # 2. 데이터베이스 초기화 (샘플 데이터 포함)
# python -m scripts.init_db

# 3. 서버 시작
uvicorn app.main:app --reload
```

### 3단계: 테스트 시작

브라우저에서 다음 URL을 열어보세요.

** 메인 테스트 페이지**: http://localhost:8000/public/index.html

## 웹 UI로 간단히 테스트하기

### 통합 시스템 테스트

**URL**: http://localhost:8000/public/index.html

**사용법**:

1. **자연어 입력** → "전북 고창에서 농업 체험하고 관광지도 구경하고 싶어요"
2. **"슬롯 추출 및 카드 검색" 버튼 클릭** → AI가 일자리/관광지 카드 추천
3. **원하는 카드들 선택** → 마음에 드는 농장과 관광지 클릭
4. **"AI 스마트 일정 생성" 버튼 클릭** → GPT-4o가 개인 맞춤 일정 생성
5. **결과 확인** → 자연어로 된 여행 일정 확인

## 발생 가능 문제

### "API 키 오류"가 날 때

- `.env` 파일의 `OPENAI_API_KEY` 값이 올바른지 확인
- OpenAI 계정에 크레딧이 남아있는지 확인

### "데이터가 없다"는 메시지가 날 때

```bash
# 데이터베이스를 다시 초기화
python -m scripts.init_db
```

**정리**: 메인 테스트 페이지(http://localhost:8000/public/index.html)에서 자연어로 여행 계획을 입력하고, AI가 추천하는 카드를 선택한 후, 개인 맞춤 일정이 생성되는지만 확인하시면 됩니다.
