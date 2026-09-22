# KOTE 감정분류 연결

## 선택한 모델과 사용 조건

- 모델: https://huggingface.co/searle-j/kote_for_easygoing_people
- 고정 revision: `0d493bc0cbd30923751a1ae7aa34ccfbee08b88d`
- KcELECTRA 기반, 43개 감정 + `없음`의 독립적인 sigmoid 점수 출력.
- 모델 카드, KOTE 저장소, 기반 KcELECTRA에 MIT가 명시돼 있다.
  저작권·허가 고지를 `THIRD_PARTY_NOTICES.md`에 보존했다.
- 공개 라이선스 조건상 상업적 이용이 허용된다. 이는 원본 댓글 전체의
  권리까지 개별 확인했다는 뜻은 아니다. 앱에 학습 댓글을 재배포하지 않는다.
- 공식 저장소의 easygoing 모델 Macro F1은 약 0.55. 정답률 55%가 아니며,
  아래 6종 변환 및 오또 일기/STT 입력의 성능 수치가 아니다.
- ALBERT/AI Hub 체크포인트를 로드하거나 호출하지 않는다.

출처: [KOTE](https://github.com/searle-j/KOTE),
[논문](https://aclanthology.org/2024.lrec-main.1499/),
[KcELECTRA](https://huggingface.co/beomi/KcELECTRA-base).

## 설치와 실행

백엔드 루트에서 Python 3.11 가상환경을 활성화한다.

```powershell
python -m pip install -r requirements-kote.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows CPU 환경에서는 먼저 공식 CPU wheel을 설치할 수 있다.

```powershell
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-kote.txt
```

기존 `requirements.txt`만 설치하면 KOTE 의존성은 설치되지 않는다.
실제 감정분류가 필요한 서버에는 **requirements-kote.txt 설치가 필수**다.
모델은 첫 분석 때 약 500 MB를 내려받고 프로세스 내에서 재사용한다.
첫 호출의 다운로드 대기시간을 피하려면 서비스 시작 전에 아래 검증 명령으로 준비한다.

```powershell
python -m scripts.smoke_kote
```

기본값은 CPU, 캐시는 `.cache/kote`이며 Git에서 제외된다.
캐시 준비 후 `KOTE_LOCAL_FILES_ONLY=true`로 실행하면 오프라인 추론한다.
GPU를 사용하려면 CUDA용 PyTorch 설치 후 `KOTE_DEVICE=cuda`를 지정한다.
모델 로딩/추론 실패는 503을 반환한다. 키워드 분류기로 몰래 전환하지 않는다.
키워드 클래스는 기존 경량 테스트용으로만 남겼다.

업스트림은 `.bin`만 제공한다. 고정 revision과 `weights_only=True`,
`trust_remote_code=False`를 사용하며 임의 모델 저장소 코드를 실행하지 않는다.
서버에서 로컬 추론하므로 일기 본문은 Hugging Face로 전송하지 않는다.

## 팀 공통 출력: 6종 유지

`기쁨`, `슬픔`, `분노`, `불안`, `상처`, `당황`을 그대로 유지한다.
새 44종 체계를 앱이나 다른 팀원의 API에 요구하지 않는다.

**변환 버전 `oddo-six-v1`은 프로젝트의 잠정 대응표이며, 학습된 6종 모델이 아니다.**

| 출력 | 사용한 KOTE 항목 |
|---|---|
| 기쁨 | 환영/호의, 감동/감탄, 고마움, 기대감, 뿌듯함, 편안/쾌적, 아껴주는, 즐거움/신남, 흐뭇함(귀여움/예쁨), 행복, 기쁨, 안심/신뢰 |
| 슬픔 | 슬픔, 절망, 서러움 |
| 분노 | 불평/불만, 지긋지긋, 화남/분노, 짜증, 증오/혐오 |
| 불안 | 공포/무서움, 불안/걱정, 부담/안_내킴 |
| 상처 | 안타까움/실망, 패배/자기혐오 |
| 당황 | 부끄러움, 어이없음, 당황/난처, 경악, 놀람 |

존경, 우쭐댐/무시함, 비장함, 의심/불신, 신기함/관심, 한심함,
역겨움/징그러움, 귀찮음, 힘듦/지침, 깨달음, 죄책감, 재미없음,
불쌍함/연민은 6종과 동등하다고 단정하기 어려워 변환에서 제외한다.
따라서 예를 들어 피로만 뚜렷한 글은 6종 기준으로 판단 불가일 수 있다.

계산 순서:

1. 각 그룹의 최대 sigmoid 점수를 사용한다. 항목 수가 많은 그룹이 합산으로 유리해지는 것을 피한다.
2. 그룹 최고점이 문턱값(기본 0.4) 미만이거나 `없음` 점수가 그 이상이면 판단 불가다.
3. 문턱값 이상의 그룹만 남기고 합이 1이 되도록 정규화한다. 복합 감정을 허용한다.
4. 판단 불가일 때도 키는 정확히 6개이며 모두 0이다. 대표 감정은 null, 키워드는 빈 목록이다.

`scores`는 상대적인 표시/호환용 값이며 실제 감정 강도나 보정된 확률이 아니다.
`confidence`는 대표 그룹의 정규화 전 근거 점수다. 이를 이용하는 기존 fusion 강도식도
검증된 감정 측정 수식이 아닌 잠정 규칙이다. 6종 대응표·문턱값은 별도 일기 평가셋으로 검증해야 한다.

## API

### POST /analyze/text

```json
{"text": "내일 발표가 있어서 긴장되고 걱정돼."}
```

응답은 `scores`(6개 키), `dominant_emotion`(6종 중 하나 또는 null),
`confidence`, `model_id`, `model_revision`, `mapping_version`이다.
빈 글/공백/1만 자 초과는 422. 모델 사용 불가는 503과 `text_emotion_unavailable` 코드다.

### POST /diary/step2/analyze

기존 multipart 필드와 응답 필드를 유지하며 내부 텍스트 분류기만 KOTE로 변경한다.
`text_emotion_scores`는 동일한 6종 점수, `emotion_scores`는 이를 0~100으로 환산한다.
판단 불가는 `emotion_keywords=[]`, `emotion_intensity=0`으로 응답한다.
이는 감정이 없다는 확정이 아니라 분류할 근거가 부족하다는 표시다.

긴 글은 최대 512 토큰(특수 토큰 포함) 단위로 나누고 각 구간의 sigmoid를
내용 토큰 수로 가중 평균한다. 첫 512 토큰만 사용하는 누락은 방지하지만,
구간을 넘는 문맥이나 '과거에는 슬펐으나 지금은 기쁨'의 시간적 의미까지 보장하지 않는다.
한 요청은 최대 1만 자·64구간으로 제한된다.

## 검증 범위

- `python -m pytest -q`: 대응표, 판단 불가, 복합 감정, 잘못된 점수,
  긴 글의 뒷부분 포함, API 입력 검증/503, 기존 서버 기능 회귀 테스트.
- `python -m scripts.smoke_kote`: 실제 가중치를 사용한 텍스트 API 및 Step2 호출.
  기본 단위 테스트는 가중치를 다운로드하지 않는다.
- 예시 문장의 추론 성공은 정확도 평가가 아니다. 오또용 독립 평가셋의
  감정별 F1·Macro F1은 아직 측정하지 않았다.

### 2026-09-16 실제 CPU 추론 관찰

캐시된 가중치로 텍스트 API 5건 및 Step2 합성 미디어 요청 1건이 모두 200을 반환했다.
행복/불안/상처 예시는 각각 해당 대표 감정으로 나왔다.
반면 `오늘은 월요일이고 책상 위에 연필이 세 자루 있다.`는 **기쁨으로 오탐**했다.
중립 문장의 오탐을 방지한다고 보장하지 않는다. 길게 반복한 중립 문장 뒤에
슬픔 문장 하나를 붙인 경우는 구간 평균으로 희석되어 판단 불가였다.
이 사례들은 모델/집계의 한계를 기록한 것이며, 이 예시에 맞춰 문턱값을 튜닝하지 않았다.
짧은 문장의 로딩 후 응답은 이 PC에서 약 0.04~0.07초, 1,858자 예시는 약 0.66초였다.
장비·문장 길이·동시 요청에 따라 달라지며 서비스 지연시간 보장은 아니다.

### 공식 시험셋 평가

`python -m scripts.evaluate_kote`로 공식 시험 데이터 5,000건을 평가한다.
먼저 `requirements-kote.txt` 설치와 모델 캐시 준비가 필요하다.
데이터는 고정된 버전에서 내려받으며 원문과 개별 예측은 `.cache/`에만 저장한다.

[2026-09-16 평가 보고서](evaluations/kote-test-2026-09-16.md):
44종 Macro F1 0.5532(문턱값 0.3), 기존 6종 변환 Macro F1 0.7348(0.4).
6종 수치는 동일 대응표로 정답을 변환한 참고 평가다. 오또 일기의 독립적인
6종 정답률로 해석할 수 없다. 슬픔·불안의 재현율이 낮아 실사용 검증이 필요하다.
