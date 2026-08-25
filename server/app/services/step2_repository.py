"""users/{uid}/diaries/{yyyy-MM-dd} 문서에 Step2 fusion 결과 병합 저장 — 자리만 잡아둔 상태.

Firestore 서비스 계정 키가 아직 없어(README.md "Firestore 쓰기 설정" 참고) 실제 쓰기는
미구현이다. routes/step2.py는 이 함수를 아직 호출하지 않는다.

FusionResult → diaries 필드 매핑 (FIRESTORE_SCHEMA.md §2 diaries 기준):
  - emotion_keywords → emotionKeywords (string[])
  - emotion_intensity → emotionIntensity (int 0-100)
  emotionStability는 이 fusion 파이프라인이 아직 계산하지 않는 지표라 매핑 대상에서 제외.

TODO(Firestore 키 확보 후):
  1. app/core/firestore_client.get_firestore_client() 재사용
  2. users/{uid}/diaries/{date} 문서에 set(merge=True)로 emotionKeywords/emotionIntensity만
     병합 — transcript/summary/videoUrl 등 Step1·Step3가 채운 다른 필드를 덮어쓰면 안 되므로
     merge=True 필수 (baseline_repository.save_baseline_profile은 문서 전체를 쓰지만, 여긴
     diaries 문서를 다른 Step들과 공유하기 때문에 다르다)
  3. routes/step2.py의 analyze_step2()에서 이 함수를 호출하도록 연결하고, user_id/date를
     받는 Form 필드를 실제로 사용하도록 바꾸기
"""

from app.services.fusion import FusionResult


def save_step2_fusion_result(user_id: str, date: str, result: FusionResult) -> None:
    raise NotImplementedError(
        "Firestore 서비스 계정 키 확보 후 구현 예정 — README.md 'Firestore 쓰기 설정' 참고"
    )
