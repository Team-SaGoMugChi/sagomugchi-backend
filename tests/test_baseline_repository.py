from app.models.baseline import BaselineProfile
from app.services import baseline_repository


class _FakeDocRef:
    def __init__(self) -> None:
        self.set_calls: list[dict] = []

    def set(self, data: dict) -> None:
        self.set_calls.append(data)


class _FakeCollectionRef:
    def __init__(self) -> None:
        self.documents: dict[str, "_FakeDocumentRef"] = {}

    def document(self, doc_id: str) -> "_FakeDocumentRef":
        return self.documents.setdefault(doc_id, _FakeDocumentRef())


class _FakeDocumentRef(_FakeDocRef):
    def __init__(self) -> None:
        super().__init__()
        self._sub_collections: dict[str, _FakeCollectionRef] = {}

    def collection(self, name: str) -> _FakeCollectionRef:
        return self._sub_collections.setdefault(name, _FakeCollectionRef())


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollectionRef] = {}

    def collection(self, name: str) -> _FakeCollectionRef:
        return self._collections.setdefault(name, _FakeCollectionRef())


def test_save_baseline_profile_writes_expected_path_and_fields(monkeypatch):
    fake_client = _FakeFirestoreClient()
    monkeypatch.setattr(baseline_repository, "get_firestore_client", lambda: fake_client)

    profile = BaselineProfile(
        user_id="user-abc",
        voice={"pitchMean": 220.0, "speechRate": 3.2, "energyMean": 0.05},
        face={"eyeAspectRatio": 0.3, "mouthAspectRatio": 0.1, "mouthWidthRatio": 0.6, "eyebrowRaiseRatio": 0.2},
        measured_at="2026-08-11T12:00:00+00:00",
    )

    baseline_repository.save_baseline_profile(profile)

    # users/{uid}/meta/baseline 경로 그대로 찾아가는지 (FIRESTORE_SCHEMA.md §2)
    doc_ref = fake_client.collection("users").document("user-abc").collection("meta").document("baseline")

    assert doc_ref.set_calls == [
        {
            "voice": profile.voice,
            "face": profile.face,
            "measuredAt": profile.measured_at,
            "featureVersion": 1,
        }
    ]
