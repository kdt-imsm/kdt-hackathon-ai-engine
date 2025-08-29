"""
app/recommendation/user_matching.py
===================================
사용자 선호도 매칭 및 프로필 선택 시스템

* 기능
  1. 자연어 입력과 dummy_prefer.csv 사용자 선호도 간 유사도 계산
  2. 가장 유사한 사용자 프로필 선택
  3. 선호도 태그 기반 스코어링
"""

import csv
import math
from typing import List, Tuple, Dict, Optional
from pathlib import Path
from app.embeddings.embedding_service import embed_texts


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """두 벡터 간의 코사인 유사도를 계산합니다."""
    if len(vec1) != len(vec2):
        return 0.0
    
    # 내적 계산
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    
    # 벡터 크기 계산
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0.0 or magnitude2 == 0.0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


# 글로벌 캐시
_preference_data: Optional[List[Dict]] = None
_preference_vectors: Optional[Dict[int, List[float]]] = None


def load_preference_data() -> List[Dict]:
    """dummy_prefer.csv 데이터를 로드하고 캐시합니다."""
    global _preference_data
    
    if _preference_data is None:
        csv_path = Path(__file__).parent.parent.parent / "data" / "dummy_prefer.csv"
        _preference_data = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 태그 문자열을 리스트로 변환
                terrain_tags = [tag.strip() for tag in str(row['terrain_tags']).split(';')] if row['terrain_tags'] else []
                activity_tags = [tag.strip() for tag in str(row['activity_style_tags']).split(';')] if row['activity_style_tags'] else []
                
                row_data = {
                    'user_id': int(row['user_id']),
                    'email': row['email'],
                    'terrain_tags': row['terrain_tags'],
                    'activity_style_tags': row['activity_style_tags'],
                    'terrain_list': terrain_tags,
                    'activity_list': activity_tags
                }
                _preference_data.append(row_data)
    
    return _preference_data


def get_preference_vectors() -> Dict[int, List[float]]:
    """사용자별 선호도 벡터를 생성하고 캐시합니다."""
    global _preference_vectors
    
    if _preference_vectors is None:
        data = load_preference_data()
        _preference_vectors = {}
        
        # 배치로 임베딩 생성 (성능 최적화)
        all_preference_texts = []
        user_ids = []
        
        for row in data:
            terrain_tags = row['terrain_list']
            activity_tags = row['activity_list']
            combined_text = " ".join(terrain_tags + activity_tags)
            all_preference_texts.append(combined_text)
            user_ids.append(row['user_id'])
        
        # 배치 임베딩 생성
        if all_preference_texts:
            vectors = embed_texts(all_preference_texts)
            for user_id, vector in zip(user_ids, vectors):
                _preference_vectors[user_id] = vector
    
    return _preference_vectors


def calculate_preference_similarity(
    user_query: str,
    activity_tags: List[str],
    region_prefs: List[str]
) -> List[Tuple[int, float, Dict]]:
    """
    사용자 입력과 선호도 데이터 간 유사도를 계산합니다.
    
    Parameters
    ----------
    user_query : str
        사용자의 자연어 입력
    activity_tags : List[str]
        슬롯에서 추출된 활동 태그
    region_prefs : List[str]
        슬롯에서 추출된 지역 선호도
        
    Returns
    -------
    List[Tuple[int, float, Dict]]
        (user_id, 유사도_점수, 사용자_정보) 튜플 리스트, 유사도 순 정렬
    """
    data = load_preference_data()
    preference_vectors = get_preference_vectors()
    
    # 사용자 입력을 벡터로 변환
    combined_input = f"{user_query} {' '.join(activity_tags)} {' '.join(region_prefs)}"
    query_vector = embed_texts([combined_input])[0]
    
    similarities = []
    
    for row in data:
        user_id = row['user_id']
        
        if user_id not in preference_vectors:
            continue
            
        # 벡터 유사도 계산 (코사인 유사도)
        pref_vector = preference_vectors[user_id]
        vector_sim = cosine_similarity(query_vector, pref_vector)
        
        # 활동 태그 매칭 점수
        user_activity_tags = row['activity_list']
        activity_match_score = calculate_tag_overlap(activity_tags, user_activity_tags)
        
        # 지형 태그와 지역 선호도 매칭 점수
        user_terrain_tags = row['terrain_list']
        terrain_match_score = 0.0
        if region_prefs:
            for region in region_prefs:
                for terrain in user_terrain_tags:
                    # 간단한 키워드 매칭 (예: "바다" in region이고 "바다" in terrain)
                    if any(keyword in region.lower() for keyword in terrain.lower().split()) or \
                       any(keyword in terrain.lower() for keyword in region.lower().split()):
                        terrain_match_score = max(terrain_match_score, 0.8)
        
        # 복합 점수 계산
        combined_score = (
            0.5 * vector_sim +           # 벡터 유사도 50%
            0.3 * activity_match_score + # 활동 매칭 30%
            0.2 * terrain_match_score    # 지형 매칭 20%
        )
        
        user_info = {
            'email': row['email'],
            'terrain_tags': row['terrain_list'],
            'activity_tags': row['activity_list'],
            'vector_sim': vector_sim,
            'activity_match': activity_match_score,
            'terrain_match': terrain_match_score
        }
        
        similarities.append((user_id, combined_score, user_info))
    
    # 유사도 순으로 정렬
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities


def calculate_tag_overlap(tags1: List[str], tags2: List[str]) -> float:
    """두 태그 리스트 간의 겹치는 정도를 계산합니다."""
    if not tags1 or not tags2:
        return 0.0
    
    set1 = set(tag.lower().strip() for tag in tags1)
    set2 = set(tag.lower().strip() for tag in tags2)
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def create_user_profile_from_preferences(
    user_query: str,
    terrain_tags: List[str],
    activity_tags: List[str],
    job_tags: List[str]
) -> Dict:
    """
    사용자가 직접 입력한 선호도로 사용자 프로필을 생성합니다.
    
    Parameters
    ----------
    user_query : str
        사용자의 자연어 입력
    terrain_tags : List[str]
        지형 선호도 태그 (1단계)
    activity_tags : List[str]
        활동 스타일 태그 (2단계)
    job_tags : List[str]
        농업 일자리 종류 태그 (3단계)
        
    Returns
    -------
    Dict
        사용자 프로필 정보
    """
    from app.embeddings.embedding_service import embed_texts
    
    # 모든 선호도를 조합하여 벡터 생성
    combined_preferences = terrain_tags + activity_tags + job_tags
    combined_text = f"{user_query} {' '.join(combined_preferences)}"
    
    user_vector = embed_texts([combined_text])[0]
    
    return {
        'user_id': 1,  # 실시간 사용자
        'terrain_tags': terrain_tags,
        'activity_tags': activity_tags,
        'job_tags': job_tags,
        'combined_preferences': combined_preferences,
        'user_vector': user_vector,
        'query': user_query
    }

def get_best_matching_user(
    user_query: str,
    activity_tags: List[str],
    region_prefs: List[str],
    top_k: int = 1
) -> Tuple[int, float, Dict]:
    """
    가장 유사한 사용자 프로필을 반환합니다.
    
    Returns
    -------
    Tuple[int, float, Dict]
        (user_id, 유사도_점수, 사용자_정보)
    """
    similarities = calculate_preference_similarity(user_query, activity_tags, region_prefs)
    
    if not similarities:
        # 기본 사용자 반환 (첫 번째 사용자)
        data = load_preference_data()
        first_user = data[0]
        return (
            first_user['user_id'], 
            0.5, 
            {
                'email': first_user['email'],
                'terrain_tags': first_user['terrain_list'],
                'activity_tags': first_user['activity_list'],
                'vector_sim': 0.5,
                'activity_match': 0.0,
                'terrain_match': 0.0
            }
        )
    
    return similarities[0] if top_k == 1 else similarities[:top_k]


def get_user_preference_vector(user_id: int) -> Optional[List[float]]:
    """특정 사용자의 선호도 벡터를 반환합니다."""
    preference_vectors = get_preference_vectors()
    return preference_vectors.get(user_id)


def enhance_user_vector_with_preferences(
    base_vector: List[float],
    user_id: int,
    preference_weight: float = 0.3
) -> List[float]:
    """
    기본 벡터에 사용자 선호도 벡터를 결합합니다.
    
    Parameters
    ----------
    base_vector : List[float]
        슬롯 기반으로 생성된 기본 벡터
    user_id : int
        매칭된 사용자 ID
    preference_weight : float
        선호도 벡터의 가중치 (0.0~1.0)
        
    Returns
    -------
    List[float]
        결합된 벡터
    """
    pref_vector = get_user_preference_vector(user_id)
    
    if pref_vector is None:
        return base_vector
    
    # 가중 평균으로 벡터 결합
    enhanced_vector = []
    for i in range(len(base_vector)):
        combined_val = (
            (1 - preference_weight) * base_vector[i] + 
            preference_weight * pref_vector[i]
        )
        enhanced_vector.append(combined_val)
    
    return enhanced_vector