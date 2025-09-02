"""
벡터 기반 통합 추천 엔진
사용자의 자연어 입력과 선호도를 종합하여 농가+관광지 추천

핵심 기능:
1. 사용자 프로필 벡터 생성/업데이트
2. 하이브리드 추천 (벡터 유사도 + 키워드 매칭)
3. 개인화된 추천 결과 생성
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import numpy as np
from app.db.models import User, TourSpot, JobPost
from app.embeddings.embedding_service import embed_text, average_embeddings
from .vector_similarity_service import VectorSimilarityService, get_vector_similarity_service

class VectorRecommendationEngine:
    """벡터 기반 개인화 추천 엔진"""
    
    def __init__(self):
        self.vector_service = get_vector_similarity_service()
    
    def create_user_preference_vector(self,
                                    db: Session,
                                    user_id: int,
                                    preference_inputs: List[str]) -> List[float]:
        """
        사용자 선호도 입력들로부터 개인화 벡터 생성
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            preference_inputs: 사용자 선호도 텍스트 리스트
                예: ["자연 풍경", "체험 활동", "힐링", "사과 따기"]
        
        Returns:
            1536차원 사용자 선호도 벡터
        """
        print(f"👤 사용자 {user_id} 선호도 벡터 생성 중...")
        print(f"📝 입력 선호도: {preference_inputs}")
        
        if not preference_inputs:
            # 기본 벡터 반환 (제로 벡터)
            return [0.0] * 1536
        
        try:
            # 각 선호도를 벡터로 변환
            preference_texts = []
            for pref in preference_inputs:
                if isinstance(pref, list):
                    # 리스트인 경우 합치기
                    preference_texts.extend(pref)
                else:
                    preference_texts.append(str(pref))
            
            # 중복 제거 및 정리
            unique_prefs = list(set(preference_texts))
            print(f"🔧 정리된 선호도: {unique_prefs}")
            
            # 벡터 생성
            from app.embeddings.embedding_service import embed_texts
            pref_vectors = embed_texts(unique_prefs)
            
            # 평균 벡터 계산
            user_vector = average_embeddings(pref_vectors)
            
            # 사용자 DB에 저장
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.pref_vector = user_vector
                db.commit()
                print(f"✅ 사용자 벡터 DB 저장 완료")
            
            print(f"✅ 사용자 선호도 벡터 생성 완료: {len(user_vector)}차원")
            return user_vector
            
        except Exception as e:
            print(f"❌ 사용자 벡터 생성 실패: {e}")
            return [0.0] * 1536
    
    def get_personalized_recommendations(self,
                                       db: Session,
                                       user_id: int,
                                       query_text: str,
                                       region: str = None,
                                       job_limit: int = 10,
                                       tour_limit: int = 10) -> Dict[str, Any]:
        """
        개인화된 농가+관광지 통합 추천
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            query_text: 자연어 검색 쿼리
            region: 지역 필터
            job_limit: 농가 추천 개수
            tour_limit: 관광지 추천 개수
        
        Returns:
            통합 추천 결과
        """
        print(f"🎯 개인화 추천 시작 - 사용자 {user_id}: '{query_text}'")
        
        # 1. 사용자 프로필 벡터 조회
        user = db.query(User).filter(User.id == user_id).first()
        user_vector = user.pref_vector if user and user.pref_vector else None
        
        if not user_vector:
            print("⚠️ 사용자 벡터 없음, 일반 벡터 검색으로 진행")
            return self._get_general_recommendations(db, query_text, region, job_limit, tour_limit)
        
        # 2. 쿼리 + 사용자 선호도 결합 벡터 생성
        combined_vector = self._create_hybrid_query_vector(query_text, user_vector)
        
        # 3. 벡터 기반 추천
        job_recommendations = self._find_similar_jobs_with_user_vector(
            db, combined_vector, region, job_limit
        )
        
        tour_recommendations = self._find_similar_tours_with_user_vector(
            db, combined_vector, region, tour_limit
        )
        
        # 4. 개인화 점수 계산
        personalized_jobs = self._calculate_personalization_scores(
            job_recommendations, user_vector, "job"
        )
        
        personalized_tours = self._calculate_personalization_scores(
            tour_recommendations, user_vector, "tour"
        )
        
        print(f"✅ 개인화 추천 완료 - 농가: {len(personalized_jobs)}개, 관광지: {len(personalized_tours)}개")
        
        return {
            "user_id": user_id,
            "query": query_text,
            "region": region,
            "jobs": personalized_jobs,
            "tours": personalized_tours,
            "recommendation_method": "vector_personalized",
            "user_vector_available": True
        }
    
    def _create_hybrid_query_vector(self, query_text: str, user_vector: List[float]) -> List[float]:
        """
        쿼리 벡터와 사용자 벡터를 결합하여 하이브리드 벡터 생성
        
        Args:
            query_text: 사용자 자연어 쿼리
            user_vector: 사용자 선호도 벡터
        
        Returns:
            결합된 하이브리드 벡터
        """
        try:
            # 쿼리를 벡터로 변환
            query_vector = embed_text(query_text)
            
            # 가중 평균 (쿼리 70%, 사용자 선호도 30%)
            query_weight = 0.7
            user_weight = 0.3
            
            query_array = np.array(query_vector, dtype=np.float32)
            user_array = np.array(user_vector, dtype=np.float32)
            
            hybrid_vector = (query_weight * query_array + user_weight * user_array).tolist()
            
            print(f"🔀 하이브리드 벡터 생성 완료 (쿼리:{query_weight}, 사용자:{user_weight})")
            return hybrid_vector
            
        except Exception as e:
            print(f"❌ 하이브리드 벡터 생성 실패: {e}")
            return user_vector  # 폴백으로 사용자 벡터 반환
    
    def _find_similar_jobs_with_user_vector(self,
                                          db: Session,
                                          hybrid_vector: List[float],
                                          region: str,
                                          limit: int) -> List[Dict[str, Any]]:
        """하이브리드 벡터로 유사한 농가 검색"""
        
        query = db.query(JobPost).filter(JobPost.pref_vector.isnot(None))
        if region:
            query = query.filter(JobPost.region == region)
        
        jobs = query.all()
        similarities = []
        
        for job in jobs:
            if not job.pref_vector:
                continue
            
            similarity = self.vector_service.calculate_cosine_similarity(
                hybrid_vector, job.pref_vector
            )
            
            similarities.append({
                'job': job,
                'similarity': similarity,
                'vector_similarity': similarity  # 원본 벡터 유사도 보존
            })
        
        # 유사도 기준 정렬
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:limit]
    
    def _find_similar_tours_with_user_vector(self,
                                           db: Session,
                                           hybrid_vector: List[float],
                                           region: str,
                                           limit: int) -> List[Dict[str, Any]]:
        """하이브리드 벡터로 유사한 관광지 검색"""
        
        query = db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None))
        if region:
            query = query.filter(TourSpot.region == region)
        
        tours = query.all()
        similarities = []
        
        for tour in tours:
            if not tour.pref_vector:
                continue
            
            similarity = self.vector_service.calculate_cosine_similarity(
                hybrid_vector, tour.pref_vector
            )
            
            similarities.append({
                'tour': tour,
                'similarity': similarity,
                'vector_similarity': similarity
            })
        
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:limit]
    
    def _calculate_personalization_scores(self,
                                        recommendations: List[Dict[str, Any]],
                                        user_vector: List[float],
                                        content_type: str) -> List[Dict[str, Any]]:
        """
        추천 결과에 개인화 점수 추가
        
        Args:
            recommendations: 벡터 검색 결과
            user_vector: 사용자 벡터
            content_type: "job" 또는 "tour"
        
        Returns:
            개인화 점수가 추가된 추천 결과
        """
        personalized_results = []
        
        for item in recommendations:
            content = item.get('job') or item.get('tour')
            if not content or not content.pref_vector:
                continue
            
            # 순수 사용자-콘텐츠 유사도 계산 (쿼리 영향 제외)
            pure_user_similarity = self.vector_service.calculate_cosine_similarity(
                user_vector, content.pref_vector
            )
            
            # 최종 개인화 점수 (벡터 유사도 + 순수 사용자 유사도)
            vector_score = item.get('similarity', 0.0)
            personalization_score = (vector_score * 0.6) + (pure_user_similarity * 0.4)
            
            # 결과 구성
            if content_type == "job":
                result = {
                    'id': content.id,
                    'title': content.title,
                    'region': content.region,
                    'address': content.address,
                    'crop_type': content.crop_type,
                    'work_date': content.work_date,
                    'work_hours': content.work_hours,
                    'tags': content.tags,
                    'image_url': content.image_url,
                    'scores': {
                        'vector_similarity': vector_score,
                        'user_preference': pure_user_similarity,
                        'personalization_score': personalization_score
                    },
                    'recommendation_reason': self._generate_recommendation_reason(
                        content, vector_score, pure_user_similarity
                    )
                }
            else:  # tour
                result = {
                    'id': content.id,
                    'name': content.name,
                    'region': content.region,
                    'tags': content.tags,
                    'lat': content.lat,
                    'lon': content.lon,
                    'contentid': content.contentid,
                    'image_url': content.image_url,
                    'keywords': content.keywords,
                    'scores': {
                        'vector_similarity': vector_score,
                        'user_preference': pure_user_similarity,
                        'personalization_score': personalization_score
                    },
                    'recommendation_reason': self._generate_recommendation_reason(
                        content, vector_score, pure_user_similarity
                    )
                }
            
            personalized_results.append(result)
        
        # 개인화 점수 기준 재정렬
        personalized_results.sort(key=lambda x: x['scores']['personalization_score'], reverse=True)
        
        return personalized_results
    
    def _generate_recommendation_reason(self,
                                      content: Any,
                                      vector_score: float,
                                      user_score: float) -> str:
        """추천 이유 생성"""
        
        if vector_score > 0.8 and user_score > 0.8:
            return "쿼리와 매우 관련성이 높고, 사용자 선호도와도 완벽히 일치합니다"
        elif vector_score > 0.8:
            return "검색 내용과 매우 관련성이 높습니다"
        elif user_score > 0.8:
            return "사용자의 선호도와 매우 잘 맞습니다"
        elif (vector_score + user_score) / 2 > 0.7:
            return "검색 의도와 개인 취향을 종합적으로 고려한 추천입니다"
        else:
            return "관련성이 있는 추천입니다"
    
    def _get_general_recommendations(self,
                                   db: Session,
                                   query_text: str,
                                   region: str,
                                   job_limit: int,
                                   tour_limit: int) -> Dict[str, Any]:
        """사용자 벡터가 없을 때 일반 추천"""
        
        print("🔄 일반 벡터 검색으로 진행")
        
        # 기본 벡터 검색 사용
        job_results = self.vector_service.find_similar_jobs_by_vector(
            db, query_text, region, job_limit, similarity_threshold=0.6
        )
        
        tour_results = self.vector_service.find_similar_tours_by_vector(
            db, query_text, region, tour_limit, similarity_threshold=0.6
        )
        
        return {
            "query": query_text,
            "region": region,
            "jobs": job_results,
            "tours": tour_results,
            "recommendation_method": "vector_general",
            "user_vector_available": False
        }
    
    def explain_recommendation_system(self) -> Dict[str, Any]:
        """추천 시스템 설명"""
        
        return {
            "system_name": "벡터 기반 개인화 추천 엔진",
            "embedding_model": "OpenAI text-embedding-3-small",
            "vector_dimension": 1536,
            "similarity_metric": "코사인 유사도",
            "workflow": {
                "step_1": "사용자 선호도를 1536차원 벡터로 변환",
                "step_2": "자연어 쿼리를 벡터로 변환",
                "step_3": "사용자 벡터와 쿼리 벡터를 가중 평균으로 결합 (쿼리 70%, 선호도 30%)",
                "step_4": "PostgreSQL + pgvector로 코사인 유사도 검색",
                "step_5": "벡터 유사도 + 개인 선호도를 결합한 개인화 점수 계산",
                "step_6": "최종 점수 기준으로 추천 결과 반환"
            },
            "advantages": [
                "키워드 매칭의 한계를 넘어 의미적 유사성 이해",
                "다양한 표현 방식에 대한 유연한 대응 ('사과 체험' ↔ '과수원 일손돕기')",
                "사용자 개인 선호도를 학습하여 점진적 개인화",
                "새로운 콘텐츠에도 즉시 적용 가능한 확장성"
            ],
            "example_query_understanding": {
                "input": "김제에서 사과따기 체험하고 싶어",
                "vector_process": "자연어 → 1536차원 벡터 → 관광지 벡터들과 유사도 비교",
                "semantic_matching": [
                    "사과따기 ↔ 과수원 체험",
                    "체험 ↔ 농업 관광",
                    "김제 ↔ 전북 김제시"
                ]
            }
        }


# 싱글톤 인스턴스
_recommendation_engine = None

def get_vector_recommendation_engine() -> VectorRecommendationEngine:
    """VectorRecommendationEngine 싱글톤 반환"""
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = VectorRecommendationEngine()
    return _recommendation_engine