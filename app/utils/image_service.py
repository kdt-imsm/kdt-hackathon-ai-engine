"""
온디맨드 이미지 수집 서비스
실시간으로 TourAPI에서 이미지를 가져와 캐싱하는 모듈
"""

import time
from typing import Optional, Dict, List
from scripts.tour_api_loader import fetch_detail_image
from app.utils.caching import get_cache, set_cache


class OnDemandImageService:
    """실시간 이미지 수집 및 캐싱 서비스"""
    
    def __init__(self, cache_ttl: int = 3600):  # 1시간 캐시
        self.cache_ttl = cache_ttl
        
    def get_image_url(self, contentid: str, tour_name: str = "") -> Optional[str]:
        """
        단일 관광지 이미지 URL 가져오기 (캐싱 적용)
        
        Parameters
        ----------
        contentid : str
            TourAPI contentid
        tour_name : str, optional
            관광지 이름 (로깅용)
            
        Returns
        -------
        Optional[str]
            이미지 URL 또는 None
        """
        if not contentid:
            return None
            
        # 캐시 키 생성
        cache_key = f"tour_image:{contentid}"
        
        # 캐시에서 확인
        cached_url = get_cache(cache_key)
        if cached_url is not None:
            return cached_url if cached_url != "NO_IMAGE" else None
        
        try:
            # TourAPI에서 실시간 수집
            image_url = fetch_detail_image(contentid)
            
            # 캐시에 저장 (없으면 "NO_IMAGE"로 표시)
            cache_value = image_url if image_url else "NO_IMAGE"
            set_cache(cache_key, cache_value)
            
            if image_url:
                print(f"✅ 이미지 수집 성공: {tour_name[:20]} - {image_url[:50]}...")
            else:
                print(f"❌ 이미지 없음: {tour_name[:20]}")
                
            return image_url
            
        except Exception as e:
            print(f"⚠️ 이미지 수집 실패: {tour_name[:20]} - {e}")
            # 실패도 캐시에 저장하여 반복 호출 방지
            set_cache(cache_key, "NO_IMAGE")  # 캐시에 저장
            return None
    
    def get_images_batch(self, contentids: List[str], tour_names: List[str] = None) -> Dict[str, Optional[str]]:
        """
        여러 관광지 이미지 URL 배치 수집
        
        Parameters
        ----------
        contentids : List[str]
            TourAPI contentid 리스트
        tour_names : List[str], optional
            관광지 이름 리스트 (로깅용)
            
        Returns
        -------
        Dict[str, Optional[str]]
            contentid -> image_url 매핑
        """
        if not contentids:
            return {}
        
        tour_names = tour_names or [""] * len(contentids)
        results = {}
        
        print(f"🖼️ {len(contentids)}개 관광지 이미지 수집 중...")
        
        for i, (contentid, name) in enumerate(zip(contentids, tour_names)):
            # API 호출 제한을 위한 딜레이
            if i > 0:
                time.sleep(0.1)
                
            results[contentid] = self.get_image_url(contentid, name)
        
        success_count = sum(1 for url in results.values() if url)
        print(f"📊 이미지 수집 결과: {success_count}/{len(contentids)}개 성공")
        
        return results


# 전역 서비스 인스턴스
_image_service = OnDemandImageService()

def get_image_service() -> OnDemandImageService:
    """이미지 서비스 인스턴스 반환"""
    return _image_service