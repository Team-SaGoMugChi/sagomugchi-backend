# Oddo AI Server (FastAPI)

Oddo Phase 4~5의 음성/표정 분석·LLM 오케스트레이션을 담당하는 백엔드. 자세한 배경은 루트의
`CLAUDE.md` §1, `ROADMAP.md` Phase 4~5 참고.

## 로컬 실행

```bash
cd server
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt
cp .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Android 에뮬레이터에서 로컬 서버 접근: `http://10.0.2.2:8000`
(`--dart-define=ODDO_API_BASE_URL=http://10.0.2.2:8000`)

동작 확인: `http://localhost:8000/docs` (Swagger UI), `GET /health`

## Firestore 쓰기 설정 (baseline 저장)

`/baseline`은 결과를 `users/{uid}/meta/baseline`에 직접 쓴다 (`firestore.rules`는 클라이언트
쓰기만 허용하므로, 서버는 Admin SDK로 규칙을 우회). 로컬에서 실제로 쓰려면:

1. Firebase 콘솔 → `oddo-emotion-diary` 프로젝트 → 프로젝트 설정 → 서비스 계정 → **새 비공개 키 생성**
2. 다운로드한 JSON을 `server/serviceAccountKey.json`으로 저장 (`.gitignore`에 이미 등록되어 있어 커밋되지 않음)
3. `.env`에 `GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json` 추가

키를 설정하지 않으면 `/baseline` 호출 시 Firestore 쓰기 단계에서 인증 에러가 난다 (분석 자체는
정상 동작). 서비스 계정 키가 없는 팀원은 `app/services/baseline_repository.save_baseline_profile`을
모킹해서 나머지 로직만 테스트할 수 있다 (`tests/test_baseline_repository.py` 참고).

## 테스트

```bash
pytest
```

## 폴더 구조

```
server/
  app/
    main.py            # FastAPI 앱 생성 + CORS
    core/
      config.py          # 환경변수 (Settings)
      firestore_client.py # Firebase Admin SDK 초기화
    api/
      router.py         # 전체 라우터 취합
      routes/            # health, voice, face, baseline, step2
    models/              # Pydantic 스키마 (요청/응답)
    services/            # 분석 로직 (librosa, MediaPipe, fusion)
  tests/
```

## 엔드포인트

| Method | Path | 설명 | 상태 |
|---|---|---|---|
| GET | `/health` | 헬스체크 | 완료 |
| POST | `/analyze/voice` | 음성 파일 → 피치/에너지 (librosa) | 피치·에너지 실동작, 발화속도는 STT 필요(Phase 5) |
| POST | `/analyze/face` | 이미지 → 랜드마크 검출 (MediaPipe) | 랜드마크 검출만 실동작, AU/표정 분류는 TODO |
| POST | `/baseline` | 음성+얼굴 → baseline 프로필 → `users/{uid}/meta/baseline` 저장 | 특징 추출 + Firestore 쓰기 실동작 (서비스 계정 키 필요) |
| POST | `/diary/step2/analyze` | 음성+얼굴+텍스트 → baseline 대비 Δ + fusion → 감정 키워드/점수 | 계산 실동작, **Firestore 저장은 미연결**(아래 참고) |
| POST | `/video/jobs` | 일기 원문 + Step2 감정 → Step3 숏폼 생성 작업 등록 (202, `job_id`) | 실동작 (기본 더미 모드, 실제 생성은 Vertex ADC 필요) |
| GET | `/video/jobs/{job_id}` | 영상 작업 단계·진행률·오류 조회 | 실동작 |
| GET | `/video/jobs/{job_id}/file` | 완성된 mp4 다운로드 | 실동작 (Storage 업로드는 후속) |

각 서비스 파일(`app/services/*.py`)의 `TODO(Phase 4)` 주석이 이어서 구현할 지점.

## Fusion 파이프라인 (`/diary/step2/analyze`)

일기 Step1 음성/표정을 baseline과 비교해 감정 키워드·점수를 뽑는다.

| 모듈 | 역할 | 상태 |
|---|---|---|
| `feature_maps.py` | VoiceFeatures/FaceFeatures → Firestore 스키마 키(`pitchMean` 등) 변환 | 완료 (baseline_service와 공유) |
| `baseline_delta.py` | baseline 대비 Δ 계산 (baseline/current/delta/relative_delta) | 완료 |
| `text_emotion.py` | 텍스트 → 감정 6종(AI Hub 감성대화 라벨) 분포 | **임시 키워드 사전 폴백** — ALBERT 모델은 팀 미확정(ROADMAP.md 2026-07-29)이라 `TextEmotionClassifier` 인터페이스 뒤에 플러그인으로만 자리 잡아둠 |
| `fusion.py` | 텍스트 감정 + 음성/표정 Δ → `emotion_keywords`/`emotion_scores`/`emotion_intensity` | **결합 공식은 잠정치** — 논문(`_docs/thesis.pdf`) 원본 수식은 이 환경에 PDF 렌더링 도구가 없어 확인 못 함. "카테고리는 텍스트, 강도는 Δ" 방식의 통상적인 fusion 패턴으로 구현 |

`text_emotion.py`의 `KeywordTextEmotionClassifier`와 `fusion.py`의 강도 계산은 정확도용이 아니라
배선 검증용 placeholder다. 팀이 ALBERT 체크포인트와 논문 수식을 확정하면 각각 교체하면 되고,
`baseline_delta.py`/`feature_maps.py`는 그대로 재사용된다.

### `/diary/step2/analyze` 입력/출력

baseline을 아직 Firestore에서 읽어오지 않으므로(서비스 계정 키 미보유), 호출하는 쪽이
`baseline_voice`/`baseline_face`를 JSON 문자열로 직접 넘긴다 — `/baseline` 응답의 `voice`/`face`
값을 그대로 재사용하면 된다. Firestore 연동 후엔 이 두 필드를 없애고 서버가 `user_id`로
`users/{uid}/meta/baseline`을 직접 읽도록 바꿀 예정.

```bash
curl -X POST http://localhost:8000/diary/step2/analyze \
  -F "text=오늘 정말 행복하고 신나는 하루였어" \
  -F 'baseline_voice={"pitchMean": 220.0, "energyMean": 0.35, "speechRate": 4.0}' \
  -F 'baseline_face={}' \
  -F "voice_file=@step1_recording.wav" \
  -F "face_image=@step1_frame.png"
```

응답의 `emotion_keywords`/`emotion_intensity`는 `diaries/{yyyy-MM-dd}` 문서의
`emotionKeywords`/`emotionIntensity` 필드와 1:1 대응한다 (FIRESTORE_SCHEMA.md §2).

### 저장 자리 (구조만, 아직 미구현)

`user_id`/`date` Form 필드는 받아두기만 하고 아직 안 쓴다. `app/services/step2_repository.py`에
`save_step2_fusion_result()`가 자리를 잡아뒀지만 `NotImplementedError`만 던진다 — Firestore
서비스 계정 키를 확보하면:

1. `step2_repository.py`에 `get_firestore_client()` 기반 실제 쓰기 구현 (`users/{uid}/diaries/{date}`
   문서에 `emotionKeywords`/`emotionIntensity`만 `set(merge=True)`로 병합 — Step1/Step3가 채운
   다른 필드를 덮어쓰지 않아야 하므로 `merge=True` 필수)
2. `routes/step2.py`의 `analyze_step2()` 안 TODO 주석 위치에서 그 함수를 호출하도록 연결

## Baseline 측정 유효성 검사

`POST /baseline`은 음성·얼굴 특징이 모두 유효한 경우에만 기준값을 저장합니다.
무음, 읽을 수 없는 파일, 얼굴 미검출, 비정상 숫자 값은 HTTP 422로 반환하며
기존 `users/{uid}/meta/baseline` 문서는 변경하지 않습니다.

```json
{"detail": {"code": "face_not_detected", "message": "얼굴을 확인하지 못했어요. 밝은 곳에서 얼굴을 화면 중앙에 맞춰 다시 측정해주세요."}}
```

재측정 오류 코드: `invalid_audio`, `voice_not_detected`, `invalid_face_image`,
`face_not_detected`. 앱은 새로 녹음·촬영하도록 안내해야 합니다. 연결 실패나 저장 실패는
같은 파일로 재시도할 수 있습니다.

이 검사는 측정 가능한 신호의 존재 여부만 확인합니다. 사람의 실제 발화 여부, 녹음 품질의
정확도, 감정 상태를 검증하지 않으며, 발화 속도는 DSP 근사치이고 얼굴 값은 랜드마크 비율입니다.
실기기의 마이크·카메라와 Firestore 서비스 계정으로 끝까지 저장되는지는 별도 확인이 필요합니다.

## 영상 생성 (`/video/jobs`, Step3)

`app/videomake/`는 영상 생성 모듈(videomake)을 이식한 것이다. 일기 + 감정 →
스토리보드(Gemini) → 캐릭터 시트·컷 이미지 → 영상(Veo 3.1 Fast) → 나레이션(TTS) →
ffmpeg 합성 → `final.mp4`. 연출 원칙(3인칭 관찰 시점, 클로즈업 금지 등)과 비용 가드는
모듈 안 코드가 강제한다.

생성에 수 분이 걸리므로 앱은 작업을 등록한 뒤 상태를 폴링한다.

```bash
curl -X POST http://localhost:8000/video/jobs -H 'Content-Type: application/json' \
  -d '{"text": "오늘 회의에서...", "emotion_keywords": ["슬픔"], "emotion_intensity": 58}'
# → {"job_id": "…", "status": "running", "stage": "storyboard", "progress": 0.0, …}

curl http://localhost:8000/video/jobs/<job_id>
# → status: running | done | failed, stage, progress(0~1), error, video_url
```

- **승인 게이트는 서버가 자동 통과**시킨다(앱 사용자는 컷을 검수하지 않음). 대신
  `VIDEOMAKE_MAX_COST_USD`(기본 $6)를 넘는 작업은 렌더하지 않고 `failed`가 된다.
  기본 설정(6컷×8초, Veo Fast 720p)은 작업당 약 $5다.
- 작업 상태는 메모리에만 있다. 서버를 재시작하면 진행 중이던 작업은 사라진다.
- 생성물은 `.cache/videomake/jobs/<job_id>/`에 남는다(커밋 안 됨).

**실제 생성 (Vertex AI):**

1. `ffmpeg` 설치 (`brew install ffmpeg` / Windows는 `winget install ffmpeg`)
2. `gcloud auth application-default login` — 조직 정책상 API 키가 아니라 ADC로 인증한다
3. `.env`에 `GOOGLE_CLOUD_PROJECT=<결제가 연결된 GCP 프로젝트>` 추가
4. `.env`에 `VIDEOMAKE_DUMMY=false` — **기본값은 더미 모드**라서 이 줄을 명시해야만 실제
   생성(과금)이 돈다. 이 줄이 없거나 `true`면 과금 0인 더미로 돈다. 실제 모드로 작업이
   시작되면 서버 로그에 경고가 남는다.

**스토리보드 LLM (기본 GPT):** `VIDEOMAKE_LLM_PROVIDER=openai`가 기본값이다. 영상 전용 키
`VIDEOMAKE_OPENAI_API_KEY`로 시나리오(스토리보드)만 GPT가 짠다(상담의 `LLM_API_KEY`와 용도별로 분리). 모델은 `VIDEOMAKE_OPENAI_MODEL`(기본
`gpt-5.5` — gpt-4o-mini는 연출 규칙을 자주 어겨 재요청 3회 안에 통과하지 못했다). 이미지·영상·나레이션은 그대로 Vertex를 쓰므로 실제 생성에는 GCP 설정이 여전히
필요하다. Gemini로 바꾸려면 `VIDEOMAKE_LLM_PROVIDER=gemini`. 상담용 `LLM_MODEL`(gpt-4o)은
그대로 둔다 — GPT-5 계열은 상담 코드의 `max_tokens`/`temperature`를 받지 않는다.

**더미 모드 (GCP 없이):** `.env`에 `VIDEOMAKE_DUMMY=true`. 모델을 부르지 않고 ffmpeg로
회색 이미지·단색 영상·무음 나레이션을 만들어 같은 흐름을 끝까지 돈다. 과금 0이고, 앱
Step3 화면의 진행률·재생을 확인할 때 쓴다. `ffmpeg`는 필요하다.

## 텍스트 감정분류 (KOTE)

감정분류 기본 모델은 KOTE이며 출력은 팀 공통 6종을 유지합니다.
설치: python -m pip install -r requirements-kote.txt
연동 API, 6종 대응표, 라이선스와 검증 절차: [KOTE 연동 문서](docs/KOTE.md).
