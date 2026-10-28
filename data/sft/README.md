# 상담 SFT 학습 데이터

상담봇을 프롬프트 방식에서 파인튜닝(SFT) 모델로 옮기기 위한 학습 데이터.

## 데이터 출처

GPT-4o가 쓴 CBT 상담 대화를 팀이 검수해서 쓴다. AI Hub 감성대화 말뭉치 등
공개 데이터는 이용약관상 사전 승낙 없는 영리 이용이 제한돼 사용하지 않는다.

## 형식

OpenAI 파인튜닝 형식(JSONL). 한 줄이 대화 하나.

```json
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

- `system`은 `app/services/counsel_prompt.py`의 프롬프트를 그대로 쓴다.
- 사용자 발화 4 + 상담봇 응답 4, 상담봇 응답으로 끝난다.

## 생성

```bash
python scripts/generate_sft_data.py --count 20 --out data/sft/generated.jsonl
```

이어서 실행하면 같은 파일에 덧붙는다. 목표는 150~200개.

## 검수 기준 (한 줄이라도 걸리면 그 대화는 삭제)

- [ ] 진단명, 약 이름, 치료 단정 표현이 없다
- [ ] "괜찮아질 거예요" 같은 근거 없는 위로로 대화를 닫지 않는다
- [ ] 상담봇이 한 번에 질문을 두 개 이상 던지지 않는다
- [ ] 응답이 2~3문장을 크게 넘지 않는다
- [ ] 사용자가 말하지 않은 사실을 상담봇이 지어내지 않는다
- [ ] 이모지·과장된 리액션이 없다
- [ ] 자해·자살 관련 내용이 없다 (앱의 위기 감지가 따로 처리)
- [ ] 한국어가 어색하지 않다

검수는 나눠서 한다. 1인당 50개씩 맡고, 삭제한 대화 수를 기록해 둔다.

## 학습

```bash
# 1. 정제: 규칙 위반·위기·평가 문장 겹침·중복 대화 제거 → train/val (prepare-report.md에 개수 기록)
python -X utf8 scripts/prepare_sft_data.py

# 2. 학습 시작 (기본 gpt-4o-2024-08-06, 3 epoch, seed 42) — 작업 ID는 finetune-jobs.md에 남는다
python -X utf8 scripts/finetune_counsel.py create

# 3. 진행·손실값 확인 → 끝나면 ft:... 모델 이름이 나온다
python -X utf8 scripts/finetune_counsel.py status ftjob-...
```

## 비교 평가

```bash
python -X utf8 scripts/evaluate_counsel.py --live --runs 3 --tag base
python -X utf8 scripts/evaluate_counsel.py --live --runs 3 --model ft:... --tag sft
python -X utf8 scripts/counsel_stats.py compare docs/evaluations/counsel-eval-<날짜>-base.json docs/evaluations/counsel-eval-<날짜>-sft.json
python -X utf8 scripts/counsel_stats.py export-replies <base.json> <sft.json> --n 40   # 블라인드 사람 검수
```

서비스 적용은 `.env`의 `LLM_MODEL=ft:...` (코드 수정 없음). 되돌릴 때는 `LLM_MODEL=gpt-4o`.