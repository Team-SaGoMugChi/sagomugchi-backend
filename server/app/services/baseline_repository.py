"""users/{uid}/meta/baseline 문서 저장 (FIRESTORE_SCHEMA.md §2 baseline 참고)."""

from app.core.firestore_client import get_firestore_client
from app.models.baseline import BaselineProfile


def save_baseline_profile(profile: BaselineProfile) -> None:
    client = get_firestore_client()
    doc_ref = client.collection("users").document(profile.user_id).collection("meta").document("baseline")

    doc_ref.set(
        {
            "voice": profile.voice,
            "face": profile.face,
            "measuredAt": profile.measured_at,
        }
    )
