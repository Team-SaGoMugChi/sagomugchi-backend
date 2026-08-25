"""baseline 측정 → BaselineProfile 조립 (FIRESTORE_SCHEMA.md §2 baseline 참고).

voice/face 맵의 키는 이 서버가 정의한다("AI 서버가 정의" — 스키마 문서 비고). 키 매핑은
app/services/feature_maps.py에 있다 — 일기 Step1 Δ 계산(baseline_delta.py)이 같은
매핑을 재사용해야 두 값을 비교할 수 있기 때문에 이 파일에 두지 않고 공유한다.
"""

from datetime import datetime, timezone

from app.models.baseline import BaselineProfile
from app.services.face_features import extract_face_features
from app.services.feature_maps import face_features_to_map, voice_features_to_map
from app.services.voice_features import extract_voice_features


def build_baseline_profile(user_id: str, voice_bytes: bytes, face_image_bytes: bytes) -> BaselineProfile:
    voice_features = extract_voice_features(voice_bytes)
    face_features = extract_face_features(face_image_bytes)

    return BaselineProfile(
        user_id=user_id,
        voice=voice_features_to_map(voice_features),
        face=face_features_to_map(face_features),
        measured_at=datetime.now(timezone.utc).isoformat(),
    )
