"""
app/recommendation/intelligent_recommender.py
===========================================
지능적 추천 시스템

기존 복잡한 시스템의 문제점을 해결하면서도 기술적 우수성을 유지:
1. 지능적 지역 확장 (무차별 전국 검색 → 단계별 논리적 확장)  
2. 투명한 가중치 시스템 (3개 핵심 요소로 단순화하되 유지)
3. 설명 가능한 추천 (왜 이런 결과가 나왔는지 추적 가능)
"""

from typing import List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from app.db.database import SessionLocal
from app.db.models import JobPost, TourSpot
from app.utils.location import get_intelligent_region_expansion, is_region_match, extract_sido
from app.utils.keyword_search import get_keyword_service
import json
import math

class IntelligentRecommender:
    """
    지능적 추천 시스템
    
    핵심 철학:
    - 사용자 의도를 최대한 존중 (지역 명시 시 해당 지역 우선)
    - 데이터 부족 시 점진적·논리적 확장 (무차별 확장 지양)
    - 모든 결정에 대한 설명 가능성 제공
    """
    
    def __init__(self):
        self.db = SessionLocal()
        
    def recommend_jobs_intelligently(
        self,
        user_vector: List[float],
        region_filter: Optional[List[str]] = None,
        target_count: int = 10,
        similarity_threshold: float = 0.3
    ) -> List[Tuple[JobPost, float, str]]:
        """
        지능적 일거리 추천
        
        Returns:
            List[(JobPost, 종합_점수, 추천_이유)]
        """
        print(f"지능적 일거리 추천 시작")
        print(f"   지역 필터: {region_filter}")
        print(f"   목표 개수: {target_count}")
        
        if not region_filter:
            # 지역 지정 없음 → 전국 검색
            return self._search_jobs_nationwide(user_vector, target_count, similarity_threshold)
        
        # 지역 명시 시: 단계적 지능형 확장 (사용자 의도 존중)
        print(f"    지역 우선 모드: '{region_filter}'부터 단계적 확장")
        
        accumulated_results = []
        searched_job_ids = set()
        
        # 1단계: 정확한 지역 매칭 (확장 없이)
        exact_results = self._search_jobs_in_regions_exact(
            user_vector, region_filter, similarity_threshold
        )
        
        for job, vector_score, reason in exact_results:
            if job.id not in searched_job_ids:
                final_score = self._calculate_job_score(
                    vector_score=vector_score,
                    region_weight=1.0,  # 정확 매칭 최고 가중치
                    keyword_score=0.0
                )
                
                enhanced_reason = f"{reason} • 지역정확매칭: 1.0"
                accumulated_results.append((job, final_score, enhanced_reason))
                searched_job_ids.add(job.id)
        
        print(f"     1단계: {len(accumulated_results)}개 발견 (정확 매칭)")
        
        # 2단계: 결과가 부족하면 지능적 확장
        if len(accumulated_results) < 5:  # 5개 미만이면 확장
            print(f"     결과 부족 ({len(accumulated_results)}개), 지능적 지역 확장 시작")
            expansion_levels = get_intelligent_region_expansion(region_filter)
            
            for expansion_regions, region_weight, description in expansion_levels[1:]:  # 첫 번째(정확매칭)는 건너뛰기
                print(f"      {description} (가중치: {region_weight:.1f})")
                
                level_results = self._search_jobs_in_regions(
                    user_vector, expansion_regions, similarity_threshold
                )
                
                new_count = 0
                for job, vector_score, reason in level_results:
                    if job.id not in searched_job_ids:
                        final_score = self._calculate_job_score(
                            vector_score=vector_score,
                            region_weight=region_weight,
                            keyword_score=0.0
                        )
                        
                        enhanced_reason = f"{reason} • 지역확장매칭: {region_weight:.1f}"
                        accumulated_results.append((job, final_score, enhanced_reason))
                        searched_job_ids.add(job.id)
                        new_count += 1
                
                print(f"        {new_count}개 추가 (누적: {len(accumulated_results)}개)")
                
                # 충분한 결과 확보 시 중단
                if len(accumulated_results) >= target_count:
                    print(f"      충분한 결과 확보")
                    break
        else:
            print(f"     충분한 결과 확보, 지역 확장 생략")
        
        # 점수순 정렬 후 상위 N개 반환
        accumulated_results.sort(key=lambda x: x[1], reverse=True)
        final_results = accumulated_results[:target_count]
        
        print(f"지능적 일거리 추천 완료: {len(final_results)}개")
        self._log_top_results("일거리", final_results)
        
        return final_results
    
    def recommend_tours_intelligently(
        self,
        user_vector: List[float],
        region_filter: Optional[List[str]] = None,
        activity_keywords: Optional[List[str]] = None,
        target_count: int = 10,
        similarity_threshold: float = 0.3
    ) -> List[Tuple[TourSpot, float, str]]:
        """
         지능적 관광지 추천 (키워드 매칭 부스팅 포함)
        """
        print(f" 지능적 관광지 추천 시작")
        print(f"    지역 필터: {region_filter}")
        print(f"    활동 키워드: {activity_keywords}")
        print(f"    목표 개수: {target_count}")
        
        if not region_filter:
            # 지역 지정 없음 → 전국 검색 (키워드 우선)
            return self._search_tours_nationwide_with_keywords(
                user_vector, activity_keywords, target_count, similarity_threshold
            )
        
        # 지역 명시 시: 단계적 지능형 확장 (사용자 의도 존중)
        print(f"    지역 우선 모드: '{region_filter}'부터 단계적 확장")
        
        accumulated_results = []
        searched_tour_ids = set()
        
        # 1단계: 정확한 지역 매칭 (확장 없이)
        exact_results = self._search_tours_in_regions_with_keywords_exact(
            user_vector, region_filter, activity_keywords, similarity_threshold
        )
        
        for result in exact_results:
            if len(result) == 4:
                tour, vector_score, keyword_score, reason = result
            else:
                tour, score, reason = result
                vector_score = score
                keyword_score = 0.0
                
            if tour.id not in searched_tour_ids:
                final_score = self._calculate_tour_score(
                    vector_score=vector_score,
                    region_weight=1.0,  # 정확 매칭 최고 가중치
                    keyword_score=keyword_score
                )
                
                enhanced_reason = f"{reason} • 지역정확매칭: 1.0 • 키워드점수: {keyword_score:.1f}"
                accumulated_results.append((tour, final_score, enhanced_reason))
                searched_tour_ids.add(tour.id)
        
        print(f"     1단계: {len(accumulated_results)}개 발견 (정확 매칭)")
        
        # 2단계: 결과가 부족하면 지능적 확장
        if len(accumulated_results) < 5:  # 5개 미만이면 확장
            print(f"     결과 부족 ({len(accumulated_results)}개), 지능적 지역 확장 시작")
            expansion_levels = get_intelligent_region_expansion(region_filter)
            
            for expansion_regions, region_weight, description in expansion_levels[1:]:  # 첫 번째(정확매칭)는 건너뛰기
                print(f"      {description} (가중치: {region_weight:.1f})")
                
                level_results = self._search_tours_in_regions_with_keywords(
                    user_vector, expansion_regions, activity_keywords, similarity_threshold
                )
                
                new_count = 0
                for result in level_results:
                    if len(result) == 4:
                        tour, vector_score, keyword_score, reason = result
                    else:
                        tour, score, reason = result
                        vector_score = score
                        keyword_score = 0.0
                        
                    if tour.id not in searched_tour_ids:
                        final_score = self._calculate_tour_score(
                            vector_score=vector_score,
                            region_weight=region_weight,
                            keyword_score=keyword_score
                        )
                        
                        enhanced_reason = f"{reason} • 지역확장매칭: {region_weight:.1f} • 키워드점수: {keyword_score:.1f}"
                        accumulated_results.append((tour, final_score, enhanced_reason))
                        searched_tour_ids.add(tour.id)
                        new_count += 1
                
                print(f"        {new_count}개 추가 (누적: {len(accumulated_results)}개)")
                
                # 충분한 결과 확보 시 중단
                if len(accumulated_results) >= target_count:
                    print(f"      충분한 결과 확보")
                    break
        else:
            print(f"     충분한 결과 확보, 지역 확장 생략")
        
        # 점수순 정렬 후 상위 N개 반환
        accumulated_results.sort(key=lambda x: x[1], reverse=True)
        final_results = accumulated_results[:target_count]
        
        print(f"지능적 관광지 추천 완료: {len(final_results)}개")
        self._log_top_results("관광지", final_results)
        
        return final_results
    
    def _search_jobs_in_regions(
        self, 
        user_vector: List[float], 
        regions: List[str], 
        threshold: float
    ) -> List[Tuple[JobPost, float, str]]:
        """특정 지역들에서 일거리 검색"""
        # 지역 조건 생성
        region_conditions = []
        for region in regions:
            region_conditions.append(JobPost.region.like(f'%{region}%'))
            # 시도명도 포함
            sido = extract_sido(region)
            if sido and sido != region:
                region_conditions.append(JobPost.region.like(f'%{sido}%'))
        
        # 쿼리 실행
        jobs = self.db.query(JobPost).filter(
            JobPost.pref_vector.isnot(None),
            or_(*region_conditions) if region_conditions else text('1=1')
        ).all()
        
        # 벡터 유사도 계산
        results = []
        for job in jobs:
            if job.pref_vector is not None:
                similarity = self._cosine_similarity(user_vector, job.pref_vector)
                if similarity >= threshold:
                    reason = f"벡터유사도: {similarity:.3f}"
                    results.append((job, similarity, reason))
        
        return results
    
    def _search_jobs_in_regions_exact(
        self, 
        user_vector: List[float], 
        regions: List[str], 
        threshold: float
    ) -> List[Tuple[JobPost, float, str]]:
        """특정 지역들에서 일거리 검색 (정확 매칭만, 시도 확장 없음)"""
        # 지역 조건 생성 (시도 확장 없이 정확한 매칭만)
        region_conditions = []
        for region in regions:
            region_conditions.append(JobPost.region.like(f'%{region}%'))
        
        # 쿼리 실행
        jobs = self.db.query(JobPost).filter(
            JobPost.pref_vector.isnot(None),
            or_(*region_conditions) if region_conditions else text('1=1')
        ).all()
        
        # 벡터 유사도 계산
        results = []
        for job in jobs:
            if job.pref_vector is not None:
                similarity = self._cosine_similarity(user_vector, job.pref_vector)
                if similarity >= threshold:
                    reason = f"벡터유사도: {similarity:.3f}"
                    results.append((job, similarity, reason))
        
        return results
    
    def _search_tours_in_regions_with_keywords(
        self, 
        user_vector: List[float], 
        regions: List[str], 
        keywords: Optional[List[str]], 
        threshold: float
    ) -> List[Tuple[TourSpot, float, float, str]]:
        """특정 지역들에서 관광지 검색 (키워드 매칭 포함)"""
        # 지역 조건 생성
        region_conditions = []
        for region in regions:
            region_conditions.append(TourSpot.region.like(f'%{region}%'))
            sido = extract_sido(region)
            if sido and sido != region:
                region_conditions.append(TourSpot.region.like(f'%{sido}%'))
        
        # 쿼리 실행
        tours = self.db.query(TourSpot).filter(
            TourSpot.pref_vector.isnot(None),
            or_(*region_conditions) if region_conditions else text('1=1')
        ).all()
        
        # 벡터 유사도 + 키워드 매칭 계산
        results = []
        for tour in tours:
            if tour.pref_vector is not None:
                vector_score = self._cosine_similarity(user_vector, tour.pref_vector)
                keyword_score = self._calculate_keyword_match_score(tour, keywords)
                
                if vector_score >= threshold or keyword_score > 0:
                    reason = f"벡터유사도: {vector_score:.3f}"
                    if keyword_score > 0:
                        reason += f" • 키워드매칭"
                    results.append((tour, vector_score, keyword_score, reason))
        
        return results
    
    def _search_tours_in_regions_with_keywords_exact(
        self, 
        user_vector: List[float], 
        regions: List[str], 
        keywords: Optional[List[str]], 
        threshold: float
    ) -> List[Tuple[TourSpot, float, float, str]]:
        """특정 지역들에서 관광지 검색 (정확 매칭만, 시도 확장 없음)"""
        # 지역 조건 생성 (시도 확장 없이 정확한 매칭만)
        region_conditions = []
        for region in regions:
            region_conditions.append(TourSpot.region.like(f'%{region}%'))
        
        # 쿼리 실행
        tours = self.db.query(TourSpot).filter(
            TourSpot.pref_vector.isnot(None),
            or_(*region_conditions) if region_conditions else text('1=1')
        ).all()
        
        # 벡터 유사도 + 키워드 매칭 계산
        results = []
        for tour in tours:
            if tour.pref_vector is not None:
                vector_score = self._cosine_similarity(user_vector, tour.pref_vector)
                keyword_score = self._calculate_keyword_match_score(tour, keywords)
                
                if vector_score >= threshold or keyword_score > 0:
                    reason = f"벡터유사도: {vector_score:.3f}"
                    if keyword_score > 0:
                        reason += f" • 키워드매칭"
                    results.append((tour, vector_score, keyword_score, reason))
        
        return results
    
    def _search_jobs_nationwide(
        self, 
        user_vector: List[float], 
        target_count: int, 
        threshold: float
    ) -> List[Tuple[JobPost, float, str]]:
        """전국 일거리 검색"""
        print("   전국 검색 모드")
        
        jobs = self.db.query(JobPost).filter(JobPost.pref_vector.isnot(None)).all()
        
        results = []
        for job in jobs:
            if job.pref_vector is not None:
                similarity = self._cosine_similarity(user_vector, job.pref_vector)
                if similarity >= threshold:
                    score = self._calculate_job_score(similarity, 1.0, 0.0)  # 전국 검색은 지역 가중치 1.0
                    reason = f"전국검색 • 벡터유사도: {similarity:.3f}"
                    results.append((job, score, reason))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:target_count]
    
    def _search_tours_nationwide_with_keywords(
        self, 
        user_vector: List[float], 
        keywords: Optional[List[str]], 
        target_count: int, 
        threshold: float
    ) -> List[Tuple[TourSpot, float, str]]:
        """전국 관광지 검색 (키워드 우선)"""
        print("   전국 관광지 검색 모드")
        
        tours = self.db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None)).all()
        
        results = []
        for tour in tours:
            if tour.pref_vector is not None:
                vector_score = self._cosine_similarity(user_vector, tour.pref_vector)
                keyword_score = self._calculate_keyword_match_score(tour, keywords)
                
                if vector_score >= threshold or keyword_score > 0:
                    final_score = self._calculate_tour_score(vector_score, 1.0, keyword_score)
                    reason = f"전국검색 • 벡터유사도: {vector_score:.3f}"
                    if keyword_score > 0:
                        reason += f" • 키워드매칭: {keyword_score:.3f}"
                    results.append((tour, final_score, reason))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:target_count]
    
    def _calculate_job_score(self, vector_score: float, region_weight: float, keyword_score: float) -> float:
        """
        🧮 일거리 종합 점수 계산 (투명한 3요소 가중치)
        
        가중치 분배:
        - 벡터 유사도: 70% (사용자 선호도 핵심)
        - 지역 매칭: 25% (접근성 중요)  
        - 키워드 매칭: 5% (정확성 보완)
        """
        return (vector_score * 0.70) + (region_weight * 0.25) + (keyword_score * 0.05)
    
    def _calculate_tour_score(self, vector_score: float, region_weight: float, keyword_score: float) -> float:
        """
        🧮 관광지 종합 점수 계산 (키워드 가중치 높음)
        
        가중치 분배:
        - 벡터 유사도: 60% (사용자 선호도)
        - 지역 매칭: 20% (접근성)
        - 키워드 매칭: 20% (관광지는 키워드 중요)
        """
        return (vector_score * 0.60) + (region_weight * 0.20) + (keyword_score * 0.20)
    
    def _calculate_keyword_match_score(self, tour: TourSpot, keywords: Optional[List[str]]) -> float:
        """키워드 매칭 점수 계산"""
        if not keywords:
            return 0.0
        
        score = 0.0
        tour_text = ""
        
        # 관광지 텍스트 정보 수집
        if hasattr(tour, 'keywords') and tour.keywords:
            tour_text += tour.keywords.lower() + " "
        if hasattr(tour, 'name') and tour.name:
            tour_text += tour.name.lower() + " "
        if hasattr(tour, 'tags') and tour.tags:
            tour_text += tour.tags.lower() + " "
        
        # 키워드별 매칭 점수
        for keyword in keywords:
            if keyword.lower() in tour_text:
                score += 0.2  # 각 키워드당 0.2점
        
        return min(score, 1.0)  # 최대 1.0점으로 제한
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """코사인 유사도 계산"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 * magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _log_top_results(self, content_type: str, results: List[Tuple[Any, float, str]]):
        """상위 결과 로깅"""
        print(f"   상위 {content_type} 결과:")
        for i, (item, score, reason) in enumerate(results[:3], 1):
            name = getattr(item, 'title', getattr(item, 'name', '이름없음'))
            region = getattr(item, 'region', '지역정보없음')
            print(f"      {i}. {name} ({region}) - 점수: {score:.3f}")
            print(f"         이유: {reason}")
    
    def _find_closest_matches(
        self, 
        user_vector: List[float], 
        excluded_ids: set, 
        needed_count: int, 
        content_type: str, 
        activity_keywords: Optional[List[str]] = None,
        threshold: float = 0.1
    ) -> List[Tuple[Any, float, str]]:
        """
        최근접 매칭 검색 - 데이터가 부족할 때 사용하는 최후 Fallback
        
        이 방법은 사용자가 입력한 지역에 데이터가 매우 적을 때
        전국에서 가장 유사한 콘텐츠를 찾아서 반환합니다.
        """
        print(f"   최근접 매칭 검색 시작 ({content_type})")
        
        results = []
        
        if content_type == "job":
            # 전국 일거리 전체에서 검색
            all_jobs = self.db.query(JobPost).filter(JobPost.pref_vector.isnot(None)).all()
            
            candidates = []
            for job in all_jobs:
                if job.id not in excluded_ids and job.pref_vector is not None:
                    similarity = self._cosine_similarity(user_vector, job.pref_vector)
                    if similarity >= threshold:
                        candidates.append((job, similarity))
            
            # 유사도순 정렬
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            for job, similarity in candidates[:needed_count]:
                score = self._calculate_job_score(similarity, 0.5, 0.0)  # 고른 지역 가중치
                reason = f"최근접매칭 • 벡터유사도: {similarity:.3f} • {job.region}"
                results.append((job, score, reason))
        
        elif content_type == "tour":
            # 전국 관광지 전체에서 검색
            all_tours = self.db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None)).all()
            
            candidates = []
            for tour in all_tours:
                if tour.id not in excluded_ids and tour.pref_vector is not None:
                    vector_score = self._cosine_similarity(user_vector, tour.pref_vector)
                    keyword_score = self._calculate_keyword_match_score(tour, activity_keywords)
                    
                    # 벡터 또는 키워드 매칭이 있으면 후보에 추가
                    if vector_score >= threshold or keyword_score > 0:
                        combined_score = vector_score + (keyword_score * 0.5)  # 키워드 보너스
                        candidates.append((tour, vector_score, keyword_score, combined_score))
            
            # 종합 점수순 정렬
            candidates.sort(key=lambda x: x[3], reverse=True)
            
            for tour, vector_score, keyword_score, _ in candidates[:needed_count]:
                score = self._calculate_tour_score(vector_score, 0.5, keyword_score)  # 고른 지역 가중치
                reason = f"최근접매칭 • 벡터유사도: {vector_score:.3f}"
                if keyword_score > 0:
                    reason += f" • 키워드매칭: {keyword_score:.3f}"
                reason += f" • {tour.region}"
                results.append((tour, score, reason))
        
        print(f"   최근접 매칭에서 {len(results)}개 발견")
        return results
    
    def get_system_diagnosis(self) -> dict:
        """시스템 진단 정보"""
        job_count = self.db.query(JobPost).count()
        tour_count = self.db.query(TourSpot).count()
        
        # 지역별 분포
        job_regions = self.db.execute(
            text("SELECT region, COUNT(*) as cnt FROM jobs GROUP BY region ORDER BY cnt DESC LIMIT 10")
        ).fetchall()
        
        tour_regions = self.db.execute(
            text("SELECT region, COUNT(*) as cnt FROM tour_spots GROUP BY region ORDER BY cnt DESC LIMIT 10")
        ).fetchall()
        
        return {
            "총_일거리": job_count,
            "총_관광지": tour_count,
            "주요_일거리_지역": [(r.region, r.cnt) for r in job_regions],
            "주요_관광지_지역": [(r.region, r.cnt) for r in tour_regions],
        }
    
    def close(self):
        if self.db:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 편의 함수들
def get_intelligent_recommendations(
    user_vector: List[float],
    region_filter: Optional[List[str]] = None,
    activity_keywords: Optional[List[str]] = None,
    job_count: int = 10,
    tour_count: int = 10
) -> dict:
    """
    통합 지능적 추천 함수
    """
    with IntelligentRecommender() as recommender:
        jobs = recommender.recommend_jobs_intelligently(
            user_vector=user_vector,
            region_filter=region_filter,
            target_count=job_count
        )
        
        tours = recommender.recommend_tours_intelligently(
            user_vector=user_vector,
            region_filter=region_filter,
            activity_keywords=activity_keywords,
            target_count=tour_count
        )
        
        diagnosis = recommender.get_system_diagnosis()
        
        return {
            "jobs": jobs,
            "tours": tours,
            "system_diagnosis": diagnosis,
            "explanation": {
                "job_scoring": "벡터유사도 70% + 지역매칭 25% + 키워드 5%",
                "tour_scoring": "벡터유사도 60% + 지역매칭 20% + 키워드 20%",
                "region_expansion": "정확매칭 → 별칭확장 → 시도확장 → 인접지역 순"
            }
        }