"""일기 대화 → 일기 한 편 정제 (39번 확인 화면의 "오늘의 일기").

팀 결정: 탄카츄와 나눈 대화를 일기 한 편으로 정제해 보여주고, 원래 대화는 "대화 내용
보기"로 따로 보여준다. 정제본은 **보여주기용**이다 — 감정 분석·영상 입력은 사용자 답변
원문을 그대로 쓴다(LLM이 다듬은 글을 넣으면 텍스트 감정이 달라진다).

정제 규칙의 앞 네 줄은 팀이 합의한 문장 그대로다. 나머지는 대화 형식이라 필요한 보강이다
(질문에 대한 짧은 답은 질문 없이는 뜻이 안 통한다).

LLM 키가 없거나 호출·파싱이 실패하면 None — 앱은 원 답변을 보여준다.
"""

import json
import logging
import re
from collections.abc import Sequence

from app.models.diary_interview import InterviewMessage
from app.services import llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """너는 감정 일기 앱 '오또'에서 사용자가 탄카츄와 나눈 대화를 일기 한 편으로 정리한다.

[정제 규칙]
- 1인칭 유지
- 말한 내용만 쓸 것 (해석/조언/추가 금지)
- 감정 표현은 원래 단어 그대로
- 군더더기/반복/말 더듬기만 정리하고 문장으로 이어 붙이기

[더 지킬 것]
- 일기체(~했다)로 쓴다. 감정 표현은 단어를 바꾸지 않고 끝만 맞춘다(예: "속상했어요" → "속상했다").
  1인칭도 일기체에 맞춰 "저/제가/제"를 "나/내가/내"로 쓴다.
- 탄카츄의 질문과 말은 넣지 않는다. 짧은 답은 질문의 맥락을 살려 온전한 문장으로 만든다
  (예: 탄카츄 "어디였어요?" / 사용자 "스터디룸이요" → "학교 스터디룸에서였다").
- 요약하지 않는다. 사용자가 말한 사실과 감정은 빠뜨리지 않는다. 뒤에 덧붙인 답(시간·장소·함께한 일 등)도
  알맞은 자리에 넣는다. 여러 답에 같은 사실이 나오면 한 번만 쓴다.
- 서로 다른 것을 짐작으로 같은 것으로 합치지 않는다(예: "맛집"과 "떡볶이 집"이 같은 곳이라고 말하지 않았다면 따로 쓴다).
- 말하다가 바로잡은 부분("어제… 아니 오늘")은 바로잡은 쪽만 쓴다.
- 일이 일어난 순서대로 이어 붙인다. 1~3문단.
- 사람 이름·장소 같은 고유명사는 그대로 쓴다. 음성 인식이 틀린 것 같은 말도 짐작으로 고치지 않는다.
- "없어요"처럼 대화를 마무리하는 답, 인사말은 넣지 않는다.

[출력]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{"diary": "정리한 일기"}"""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_SPEAKER_LABEL = {"oddo": "탄카츄", "user": "사용자"}


def _build_user_prompt(messages: Sequence[InterviewMessage]) -> str:
    lines = ["[대화]"]
    lines += [f"{_SPEAKER_LABEL[m.speaker]}: {m.text}" for m in messages]
    lines.append("\n위 대화에서 사용자가 한 말을 정제 규칙대로 일기 한 편으로 정리해 지정한 JSON 형식으로만 답한다.")
    return "\n".join(lines)


def _parse(raw: str) -> str:
    text = _FENCE.sub("", raw.strip()).strip()
    if text and not text.startswith("{"):
        # 형식을 어기고 일기만 평문으로 줘도 내용은 쓸 수 있다.
        return text
    diary = json.loads(text)["diary"]
    if not isinstance(diary, str) or not diary.strip():
        raise ValueError("diary must be a non-empty string")
    return diary.strip()


def refine_diary(messages: Sequence[InterviewMessage]) -> str | None:
    try:
        raw = llm_client.chat(
            SYSTEM_PROMPT,
            [{"role": "user", "content": _build_user_prompt(messages)}],
            temperature=0.3,
            max_tokens=1200,
        )
        return _parse(raw)
    except Exception as exc:
        # 키 미설정·네트워크 오류·JSON 형식 오류 — 앱이 원 답변을 보여준다.
        # 사용자 발화는 로그에 남기지 않는다.
        logger.warning("diary refine failed: %s", type(exc).__name__)
        return None
