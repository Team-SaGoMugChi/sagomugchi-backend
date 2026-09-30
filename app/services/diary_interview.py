"""일기 말하기 대화(37번 화면) — 일기 칸을 채우며, 빈 칸을 탄카츄가 자연스럽게 묻는다.

상담(counsel_prompt.py)과 역할이 다르다. 상담은 감정과 생각을 다루고, 여기는 일기를
쓰는 단계라 **이야기를 칸으로 채우는 기록 도우미**다. 상담·조언·해석은 뒤의 상담 단계에서
한다. 여기서 나온 답변은 전부 감정 분석(/diary/step2/analyze)의 입력이 되므로, 탄카츄가
감정을 짐작해 말하거나 감정 단어를 먼저 제시하면 분석이 탄카츄의 말을 따라간다 — 기분은
열린 질문으로만 묻는다.

칸
    사실(육하원칙)에 더해, 감정 분석과 영상 파트(장면 tone·turning_points·arc)에 넘길 재료로
    그때 기분·기분 변화·지금 기분을 모은다. 경과 시간(교수님 피드백)은 "언제"에 합친다 —
    얼마나 지났는지 알 수 있을 만큼 구체적이어야 채워진 것으로 본다. 칸은 사용자가 직접
    말한 것만 채운다(짐작으로 채우면 이야기를 다 하기 전에 대화가 끝난다).

흐름
    매 차례 LLM이 대화 전체에서 칸을 채우고 빈 칸 중 이야기 흐름에 맞는 것을 묻는다.
    칸이 다 차고 흐름상 마무리해도 되면 "더 하고 싶은 이야기"를 묻고(WRAP_UP), 사용자가
    더 없다고 하면 done — 앱은 원문 확인(Step2)으로 넘어간다. 칸 판정과 마무리 확인은
    서버가 강제한다. 같은 호출에서 지금까지 들은 이야기의 요약(summary)도 받는다 — 보여주기
    용이고 감정 분석 입력은 사용자 답변 원문이다(LLM이 다듬은 글을 넣으면 텍스트 감정이 달라진다).

질문은 최대 MAX_FOLLOW_UPS개. 사용자가 끝까지 답하지 않는 칸이 있어도 대화는 끝나야 한다.
키가 없거나 호출·파싱이 실패하면 고정 문구로 대신하고 경고를 남긴다 — 대화가 멈추지 않게.
"""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.models.diary_interview import InterviewMessage
from app.services import llm_client

logger = logging.getLogger(__name__)

MAX_FOLLOW_UPS = 8

# 칸 이름 → LLM에게 주는 설명. 순서는 서버가 직접 물을 칸을 고르는 우선순위이기도 하다.
SLOTS: dict[str, str] = {
    "무엇을": "무슨 일이 있었는지",
    "언제": "그 일이 있었던 때. 얼마나 지났는지 알 수 있을 만큼 (예: 오늘 오후 2시, 어제 저녁, 지난주 금요일)",
    "어디서": "장소",
    "누가": "함께 있었거나 관련된 사람 (혼자였다면 '혼자')",
    "어떻게": "일이 어떻게 흘러갔는지",
    "왜": "왜 그렇게 됐는지 (사용자가 생각하는 이유)",
    "그때 기분": "사건의 핵심 순간에 느낀 감정 (사용자가 말한 표현 그대로)",
    "기분 변화": "기분이 바뀐 순간과 계기 (바뀌지 않았다고 했다면 '변화 없음')",
    "지금 기분": "지금 그 일을 돌아보는 마음",
}

# LLM이 빈 칸을 두고 마무리해 버렸을 때 서버가 직접 묻는 말.
SLOT_QUESTIONS: dict[str, str] = {
    "무엇을": "어떤 일이 있었는지 조금 더 들려줄래요?",
    "언제": "그 일은 언제 있었어요?",
    "어디서": "어디에서 있었던 일이에요?",
    "누가": "그때 누구와 함께였어요?",
    "어떻게": "그 일은 어떻게 흘러갔어요?",
    "왜": "왜 그렇게 됐다고 생각해요?",
    "그때 기분": "그 일이 있었을 때 어떤 기분이었어요?",
    "기분 변화": "이야기하는 동안 기분이 달라진 순간이 있었어요?",
    "지금 기분": "지금 돌아보면 어떤 마음이 들어요?",
}

# 끝내기 전에 묻는 말. 탄카츄의 말에 이 구절이 들어 있으면 마무리 확인을 한 것으로 본다.
WRAP_UP_MARK = "더 하고 싶은 이야기"
WRAP_UP = "혹시 더 하고 싶은 이야기가 있어요?"

# 칸을 알 수 없을 때(LLM 실패) 차례대로 묻는 말. 마지막은 마무리 확인.
FALLBACK_QUESTIONS = (
    "그 일은 언제, 어디서 있었어요?",
    "그때 누구와 함께였어요?",
    "그 일이 있었을 때 어떤 기분이었어요?",
    "그 일은 어떻게 흘러갔어요?",
    "왜 그렇게 됐다고 생각해요?",
    "지금 돌아보면 어떤 마음이 들어요?",
    WRAP_UP,
)
CLOSING = "이야기해줘서 고마워요. 들은 이야기로 오늘 일기를 정리해볼게요."

_SLOT_GUIDE = "\n".join(f"- {name}: {desc}" for name, desc in SLOTS.items())
_SLOT_EXAMPLE = ", ".join(f'"{name}": "..." 또는 null' for name in SLOTS)

SYSTEM_PROMPT = f"""너는 감정 일기 앱 '오또'의 캐릭터 탄카츄다.
사용자가 오늘 있었던 일을 말로 일기에 남기고 있고, 너는 영상통화하듯 편하게 들으며
이야기를 일기 칸으로 채우도록 돕는다. 모은 이야기는 감정 분석과 짧은 영상 제작에 쓰인다.

[일기 칸]
{_SLOT_GUIDE}

[할 일]
1. 지금까지의 대화 전체에서 각 칸을 사용자가 말한 대로 짧게 채운다.
   칸은 사용자가 그 내용을 직접 말했을 때만 채운다. 다른 칸의 내용으로 짐작해 채우지 않는다.
   예: 무슨 일이 있었는지만 말했다면 "어떻게", "왜", 기분 칸은 null이다.
   기분 칸은 사용자가 감정을 직접 말했을 때만 채운다.
2. 빈 칸이 있으면: [방금 한 말]에 나온 구체적인 사실을 짧게 짚어 반응한 뒤, 빈 칸 중 이야기 흐름에
   가장 자연스러운 것을 묻는다. 사건 이야기가 나오면 그 순간을 콕 집어 자세히 묻는다.
   예: "팀장이 다른 얘기로 넘어갔을 때 어떤 기분이었어요?"
   가까운 두 칸(예: 언제·어디서)은 한 질문으로 물어도 된다. 이미 채운 칸은 다시 묻지 않는다.
3. 칸이 다 찼고 대화 흐름상 마무리해도 될 때(사용자가 이야기를 이어가는 중이 아닐 때):
   ready_to_wrap을 true로 하고, 짧게 반응한 뒤 "혹시 더 하고 싶은 이야기가 있어요?"라고 묻는다.
4. "더 하고 싶은 이야기"를 물은 뒤 사용자가 더 없다고 하면: finished를 true로 하고, 질문하지 않고
   들은 이야기를 한 구절로 짚으며 이야기해줘서 고맙다고 마무리한다.
   사용자가 이야기를 더 하면 짧게 반응하고 이어서 듣는다.
5. 남은 질문 수가 0이면 질문하지 않고 고맙다고 마무리한다.
6. 일기 요약(summary)을 매번 새로 쓴다. 짧은 한두 문장, 합쳐서 60자 안팎으로 핵심만 쓴다.
   칸을 다 넣으려 하지 말고, 무슨 일이 있었는지와 그 일의 핵심 흐름만 담는다.
   하루를 돌아보는 말투로 쓴다. 예(다른 이야기): "친구 생일 파티에서 케이크가 늦게 와 촛불만 켜고
   노래를 불렀던 하루였어요."
   사용자가 직접 말한 감정 표현(예: "속상했어요")은 살리고, 말하지 않은 감정이나 내용은 넣지 않는다.

[말투]
- 편한 존댓말, 두 문장 이내. 물음표는 한 번만. 매번 같은 말로 시작하지 않는다.
- 호칭을 쓰지 않는다. 이모지를 쓰지 않는다.

[하지 않을 일]
- 상담, 조언, 해석, 평가를 하지 않는다. 그건 다음 단계인 상담에서 한다.
- 감정을 추측하는 말을 하지 않는다("아쉬웠겠네요", "속상하셨겠어요", "힘드셨겠어요" 등).
  반응은 감정이 아니라 사실을 짚는다.
- 기분을 물을 때 감정 단어를 먼저 제시하지 않는다. "속상했어요?"가 아니라 "어떤 기분이었어요?"처럼 묻는다.
- 사용자가 말하지 않은 내용을 지어내지 않는다.

[출력]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{{"slots": {{{_SLOT_EXAMPLE}}}, "summary": "일기 요약", "ready_to_wrap": false, "finished": false, "reply": "탄카츄가 할 말"}}"""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# 마무리 확인에 "더 없다"고 답한 것으로 보는 짧은 말 — LLM이 finished를 놓쳐도 끝낼 수 있게.
_NOTHING_MORE = re.compile(r"^(없|아니|괜찮|다\s*했|다\s*말했|끝|이게\s*다|그게\s*다)")
_NOTHING_MORE_MAX_LEN = 15


@dataclass
class InterviewTurn:
    reply: str
    done: bool
    # 칸 이름 → 채운 내용(빈 칸은 None). 칸을 알 수 없는 차례(LLM 실패·평문 응답)면 비어 있다.
    slots: dict[str, str | None] = field(default_factory=dict)
    # 지금까지 들은 이야기의 요약(보여주기용). 못 만든 차례면 None.
    summary: str | None = None
    # LLM 판단: 칸이 다 찼고 흐름상 마무리 확인을 해도 된다.
    ready_to_wrap: bool = False
    # LLM 판단: 마무리 확인에 사용자가 더 없다고 답했다.
    finished: bool = False

    @property
    def missing(self) -> list[str]:
        """빈 칸. 칸을 알 수 없으면 빈 목록 — 빈 칸이 없다는 뜻이 아니다."""
        if not self.slots:
            return []
        return [name for name in SLOTS if not self.slots.get(name)]


def follow_ups_asked(history: Sequence[InterviewMessage]) -> int:
    """첫 사용자 발화 이후 탄카츄가 한 말의 수. 앱의 첫 인사는 세지 않는다."""
    heard_user = False
    count = 0
    for message in history:
        if message.speaker == "user":
            heard_user = True
        elif heard_user:
            count += 1
    return count


def _just_asked_wrap_up(history: Sequence[InterviewMessage]) -> bool:
    """이번 발화가 마무리 확인("더 하고 싶은 이야기")에 대한 답인지."""
    for message in reversed(history):
        if message.speaker == "oddo":
            return WRAP_UP_MARK in message.text
    return False


def _says_nothing_more(user_text: str) -> bool:
    text = re.sub(r"[\s.!?~,]+$", "", user_text.strip())
    return len(text) <= _NOTHING_MORE_MAX_LEN and bool(_NOTHING_MORE.match(text))


_SPEAKER_LABEL = {"oddo": "탄카츄", "user": "사용자"}


def _build_user_prompt(history: Sequence[InterviewMessage], user_text: str, remaining: int) -> str:
    """대화를 역할별 메시지로 넘기면 모델이 대화체로 이어 말하며 JSON 지시를 무시한다
    (gpt-4o-mini에서 확인). 상담 리포트(counsel_report.py)처럼 대화를 한 요청에 담는다."""
    lines = ["[지금까지의 대화]"]
    lines += [f"{_SPEAKER_LABEL[m.speaker]}: {m.text}" for m in history]
    lines.append(f"사용자: {user_text}")
    lines.append(f"\n[방금 한 말] {user_text}")
    lines.append(f"[남은 질문 수] {remaining}")
    lines.append("\n위 대화를 읽고 칸을 채운 뒤 탄카츄가 이어서 할 말을 지정한 JSON 형식으로만 답한다.")
    return "\n".join(lines)


def _clean_slots(raw: object) -> dict[str, str | None]:
    values = raw if isinstance(raw, Mapping) else {}
    slots: dict[str, str | None] = {}
    for name in SLOTS:
        value = values.get(name)
        slots[name] = value.strip() if isinstance(value, str) and value.strip() else None
    return slots


def _parse(raw: str) -> InterviewTurn:
    text = _FENCE.sub("", raw.strip()).strip()
    if text and not text.startswith("{"):
        # 형식을 어기고 평문으로 답해도 말 자체는 쓸 수 있다. 칸과 요약은 알 수 없다.
        return InterviewTurn(reply=text, done=False)
    data = json.loads(text)
    reply = data["reply"]
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("reply must be a non-empty string")
    summary = data.get("summary")
    return InterviewTurn(
        reply=reply.strip(),
        done=False,
        slots=_clean_slots(data.get("slots")),
        summary=summary.strip() if isinstance(summary, str) and summary.strip() else None,
        ready_to_wrap=data.get("ready_to_wrap") is True,
        finished=data.get("finished") is True,
    )


def _fallback(asked: int, remaining: int, wrapping_up: bool) -> InterviewTurn:
    if remaining > 0 and not wrapping_up and asked < len(FALLBACK_QUESTIONS):
        return InterviewTurn(reply=FALLBACK_QUESTIONS[asked], done=False)
    return InterviewTurn(reply=CLOSING, done=True)


def next_turn(history: Sequence[InterviewMessage], user_text: str) -> InterviewTurn:
    asked = follow_ups_asked(history)
    remaining = max(MAX_FOLLOW_UPS - asked, 0)
    wrapping_up = _just_asked_wrap_up(history)
    try:
        raw = llm_client.chat(
            SYSTEM_PROMPT,
            [{"role": "user", "content": _build_user_prompt(history, user_text, remaining)}],
            temperature=0.7,
            max_tokens=600,
        )
        turn = _parse(raw)
    except Exception as exc:
        # 키 미설정·네트워크 오류·JSON 형식 오류 — 대화가 멈추지 않도록 고정 문구로.
        # 사용자 발화는 로그에 남기지 않는다.
        logger.warning("diary interview fell back to a fixed line: %s", type(exc).__name__)
        return _fallback(asked, remaining, wrapping_up)

    complete = bool(turn.slots) and not turn.missing
    if remaining == 0 or (wrapping_up and (turn.finished or _says_nothing_more(user_text))):
        # 상한에 닿았거나 마무리 확인에 더 없다고 했으면 끝난다. 그런데도 LLM이 물으면
        # 대화가 끝나지 않은 것처럼 들리니 고정 인사로 바꾼다.
        turn.done = True
        if "?" in turn.reply:
            turn.reply = CLOSING
    elif complete and (turn.ready_to_wrap or "?" not in turn.reply or remaining == 1):
        # 칸이 다 찼으면 끝내기 전에 더 하고 싶은 이야기가 있는지 묻는다 — LLM이 마무리해
        # 버리거나 질문이 한 번밖에 안 남았어도 확인은 거친다.
        if WRAP_UP_MARK not in turn.reply:
            turn.reply = WRAP_UP
    elif turn.missing and "?" not in turn.reply:
        # 빈 칸이 남았는데 LLM이 마무리해 버리면 그 칸을 직접 묻는다.
        turn.reply = SLOT_QUESTIONS[turn.missing[0]]
    return turn
