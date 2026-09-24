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

## 학습 (검수 완료 후)

```bash
# 1. 파일 업로드
openai api files.create -f data/sft/generated.jsonl -p fine-tune

# 2. 학습 시작 (파일 ID는 위 결과에서)
openai api fine_tuning.jobs.create -t <file-id> -m gpt-4o-mini-2024-07-18

# 3. 상태 확인
openai api fine_tuning.jobs.list
```

학습이 끝나면 나오는 모델 이름(`ft:gpt-4o-mini:...`)을 `.env`에 넣는다.

```
LLM_MODEL=ft:gpt-4o-mini:...
```

서버를 재시작하면 상담이 학습 모델로 응답한다. 품질이 기대에 못 미치면
`LLM_MODEL=gpt-4o`로 되돌리면 된다 — 코드는 수정하지 않는다.

## 비교 방법

같은 질문 10개를 기존 모델과 학습 모델에 각각 넣고, 팀원 2명이
"어느 쪽이 더 상담답게 답했는지" 눈으로 비교한다. 결과를 이 파일 아래에 기록한다.