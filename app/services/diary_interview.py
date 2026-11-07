"""일기 말하기 대화(37번 화면) — 일기 칸을 채우며, 빈 칸을 탄카츄가 자연스럽게 묻는다.

상담(counsel_prompt.py)과 역할이 다르다. 상담은 감정과 생각을 다루고, 여기는 일기를
쓰는 단계라 **친구처럼 들으며 이야기를 칸으로 모은다**. 상담·조언·해석은 뒤의 상담 단계에서
한다. 여기서 나온 답변은 전부 감정 분석(/diary/step2/analyze)의 입력이 되므로, 탄카츄가
감정을 짐작해 말하거나 감정 단어를 먼저 제시하면 분석이 탄카츄의 말을 따라간다 — 사용자가
먼저 말한 감정 단어를 되받는 것만 허용하고, 기분은 열린 질문으로만 묻는다.

칸
    사실(육하원칙)에 더해, 감정 분석과 영상 파트(장면 tone·turning_points·arc)에 넘길 재료로
    그때 기분·기분 변화·지금 기분을 모은다. 경과 시간(교수님 피드백)은 "언제"에 합친다 —
    얼마나 지났는지 알 수 있을 만큼 구체적이어야 채워진 것으로 본다. 칸은 사용자가 직접
    말한 것만 채운다(짐작으로 채우면 이야기를 다 하기 전에 대화가 끝난다).

흐름 (#97)
    한 차례에 LLM을 두 번 부른다. 한 번에 칸 채우기·물을 칸 고르기·말 만들기를 다 시키면
    (gpt-4o-mini) 빈 칸이 아닌 걸 묻고, 방금 말한 감정을 또 묻고, 금지한 감정 짐작을 했다.
    1. 칸 추출(EXTRACT_PROMPT, JSON) — 칸·요약과 함께 "방금 감정을 말했나"·"마무리 확인에
       더 없다고 했나"를 판단만 한다.
    2. 서버가 이번에 할 일을 고른다 — 빈 칸 묻기(후보 칸까지)·맞장구·마무리 확인·끝인사.
       방금 감정을 말했거나 직전에 기분을 물었으면 기분 칸은 묻지 않는다. 맞장구는 사용자
       말이 "~했는데"처럼 이어지는 어미로 끝났을 때만 한다.
    3. 말 만들기(REPLY_PROMPT, 평문) — 고른 일만 받아 탄카츄의 한마디를 쓴다. 끝인사는
       고정 문구(CLOSINGS)에서 고른다.
    칸이 다 차면 "더 하고 싶은 이야기"를 묻고(WRAP_UP), 사용자가 더 없다고 하면 done — 앱은
    원문 확인(Step2)으로 넘어간다. 요약(summary)은 보여주기용이고 감정 분석 입력은 사용자
    답변 원문이다(LLM이 다듬은 글을 넣으면 텍스트 감정이 달라진다).

갈등 (#120)
    누군가와 부딪힌 일(말다툼·서운한 말·오해·혼남)이면 칸 추출이 conflict로 알리고, 그날만
    상대가 한 말(상대 발언)과 상대의 상황(상대 상황) 두 칸을 더 묻는다. 사용자 말만 들으면
    일기·영상·상담이 한쪽 이야기만 담는다. 상대 편을 들거나 누가 옳은지 따지지 않고 사실만
    묻는다. 갈등이 아닌 날에는 이 두 칸을 묻지도, 빈 칸(missing)으로 알리지도 않는다.

질문은 최대 MAX_FOLLOW_UPS개(갈등이면 CONFLICT_EXTRA_FOLLOW_UPS개 더). 사용자가 끝까지 답하지 않는 칸이 있어도 대화는 끝나야 한다.
키가 없거나 호출·파싱이 실패하면 고정 문구로 대신하고 경고를 남긴다 — 대화가 멈추지 않게.
"""

import json
import logging
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.models.diary_interview import InterviewMessage
from app.services import llm_client

logger = logging.getLogger(__name__)

MAX_FOLLOW_UPS = 8
# 갈등인 날 더 묻는 칸만큼 질문 상한을 늘린다. 앱이 보내는 history 상한
# (InterviewTurnRequest.history max_length)이 그만큼의 대화를 담을 수 있어야 한다.
CONFLICT_EXTRA_FOLLOW_UPS = 2

# 칸 이름 → LLM에게 주는 설명. 순서는 앱에 돌려주는 빈 칸(missing) 순서다.
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
    "상대 발언": "갈등 상대가 한 말이나 행동 (사용자가 전한 그대로)",
    "상대 상황": "갈등 상대가 그때 처해 있던 상황이나 사정 (사용자가 알거나 짐작한 대로)",
}
FEELING_SLOTS = ("그때 기분", "기분 변화", "지금 기분")
# 누군가와 부딪힌 날에만 묻는 칸.
CONFLICT_SLOTS = ("상대 발언", "상대 상황")

# 빈 칸을 묻는 순서 — 친구가 이야기를 들을 때 궁금해하는 순서(무슨 일 → 그래서 → 그 순간 마음 …).
# 앞의 두 칸을 후보로 주고 흐름에 맞는 쪽을 LLM이 고른다.
# "기분 변화"는 따로 묻지 않는다 — 그때·직후·지금 기분을 세 번 물으면 어색하다(재영 실기기
# 테스트). 그때 기분과 지금 기분을 들으면 칸 추출이 둘을 비교해 채우고, 못 채워도 마무리한다.
# 상대가 한 말은 일이 어떻게 흘러갔는지 들은 뒤, 상대의 상황은 내 기분을 들은 뒤에 묻는다.
ASK_ORDER = (
    "무엇을", "어떻게", "상대 발언", "그때 기분", "누가", "상대 상황", "언제", "어디서", "왜", "지금 기분",
)
OPTIONAL_SLOTS = ("기분 변화",)

# 말 만들기가 실패했거나 질문을 빠뜨렸을 때 서버가 직접 묻는 말.
SLOT_QUESTIONS: dict[str, str] = {
    "무엇을": "어떤 일이 있었는지 조금 더 들려줄래요?",
    "언제": "그게 언제였어요?",
    "어디서": "어디서 있었던 일이에요?",
    "누가": "그때 누구랑 같이 있었어요?",
    "어떻게": "그래서 어떻게 됐어요?",
    "왜": "왜 그렇게 된 것 같아요?",
    "그때 기분": "그 순간엔 마음이 어땠어요?",
    "기분 변화": "그러고 나서 마음이 좀 달라졌어요?",
    "지금 기분": "지금은 좀 어때요?",
    "상대 발언": "그때 상대는 뭐라고 했어요?",
    "상대 상황": "상대는 그때 어떤 상황이었던 것 같아요?",
}

# 끝내기 전에 묻는 말. 탄카츄의 말에 이 구절이 들어 있으면 마무리 확인을 한 것으로 본다.
WRAP_UP_MARK = "더 하고 싶은 이야기"
WRAP_UP = "오늘 더 하고 싶은 이야기 있어요?"

# 맞장구가 질문뿐이라 남는 말이 없을 때.
LISTENINGS = ("그랬군요. 계속 들려줘요.", "응응, 듣고 있어요.", "아하, 그다음은요.")

# 끝인사는 고정 문구에서 고른다 — LLM이 들은 이야기를 짚으면("회의에서 5분 동안 당황했던
# 일을 말해줘서 고마워요") 어색하다(재영 실기기 테스트).
CLOSINGS = (
    "오늘 이야기 들려줘서 고마워요. 들은 이야기로 일기를 정리해볼게요.",
    "이야기해줘서 고마워요. 이제 오늘 일기를 정리해볼게요.",
    "오늘 하루 들려줘서 고마워요. 일기로 정리해둘게요.",
    "말해줘서 고마워요. 들은 대로 오늘 일기를 정리해볼게요.",
    "오늘도 이야기 나눠줘서 고마워요. 일기 정리하러 가볼게요.",
)

# 칸을 알 수 없을 때(LLM 실패) 차례대로 묻는 말. 마지막은 마무리 확인.
FALLBACK_QUESTIONS = (
    "그게 언제, 어디서였어요?",
    "그때 누구랑 같이 있었어요?",
    "그 순간엔 마음이 어땠어요?",
    "그래서 어떻게 됐어요?",
    "왜 그렇게 된 것 같아요?",
    "지금은 좀 어때요?",
    WRAP_UP,
)

_SLOT_GUIDE = "\n".join(f"- {name}: {desc}" for name, desc in SLOTS.items())
_SLOT_EXAMPLE = ", ".join(f'"{name}": "..." 또는 null' for name in SLOTS)

EXTRACT_PROMPT = f"""너는 감정 일기 앱 '오또'의 기록 담당이다. 사용자와 캐릭터 탄카츄의 영상통화 대화를 읽고
일기 칸을 채운다. 너는 말하지 않는다 — 판단만 JSON으로 낸다.

[일기 칸]
{_SLOT_GUIDE}

[칸 채우기]
- 지금까지의 대화 전체에서 각 칸을 사용자가 말한 대로 짧게 채운다. 앞 차례에 말한 것도 빠뜨리지 않는다.
- 칸은 사용자가 그 내용을 직접 말했을 때만 채운다. 다른 칸의 내용으로 짐작해 채우지 않는다.
  예: 무슨 일이 있었는지만 말했다면 "어떻게", "왜", 기분 칸은 null이다.
- 한 마디에 여러 칸이 들어 있으면 모두 채운다.
  예: "엄마가 결혼 얘기를 꺼내서 짜증 나서 소리 질렀는데, 끊고 나니까 미안했어요"
  → 왜: 엄마가 결혼 얘기를 꺼냄 / 그때 기분: 짜증 남 / 기분 변화: 끊고 나니 미안해짐
- 기분 칸은 사용자가 감정을 직접 말했을 때만, 사용자가 말한 표현 그대로 채운다.
- "기분 변화"는 따로 묻지 않는다. 사용자가 말한 그때 기분·그 뒤 기분·지금 기분을 비교해 채운다.
  예: 그때 "당황스러웠어", 지금 "이제 좀 웃겨" → 기분 변화: 당황스러움 → 지금은 웃김
  예: 그때 "속상했어", 지금도 "아직 속상해" → 기분 변화: 변화 없음
- "상대 발언"·"상대 상황"은 갈등 상대에 대해 사용자가 말한 것만 채운다. 상대의 속마음을 짐작해 채우지 않는다.
  예: "친구가 약속에 늦었는데 미안하단 말도 없었어" → 상대 발언: 늦고도 미안하다는 말이 없었음 / 상대 상황: null

[판단]
- just_felt: [방금 한 말]에서 사용자가 자기 감정을 직접 말했으면 true.
- finished: 탄카츄가 "더 하고 싶은 이야기"를 물었고, 사용자가 더 없다고 답했으면 true.
- conflict: 지금까지의 이야기가 특정한 사람과 부딪힌 일(말다툼, 싸움, 서운한 말을 들음, 오해, 혼남,
  의견 충돌)이면 true. 그 사람과 함께 있었을 뿐이거나 혼자 겪은 일이면 false.

[요약]
일기 요약(summary)을 매번 새로 쓴다. 짧은 한두 문장, 합쳐서 60자 안팎으로 핵심만 쓴다.
칸을 다 넣으려 하지 말고, 무슨 일이 있었는지와 그 일의 핵심 흐름만 담는다.
하루를 돌아보는 말투로 쓴다. 예(다른 이야기): "친구 생일 파티에서 케이크가 늦게 와 촛불만 켜고
노래를 불렀던 하루였어요."
사용자가 직접 말한 감정 표현(예: "속상했어요")은 살리고, 말하지 않은 감정이나 내용은 넣지 않는다.

[출력]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{{"slots": {{{_SLOT_EXAMPLE}}}, "summary": "일기 요약", "just_felt": false, "finished": false, "conflict": false}}"""

REPLY_PROMPT = """너는 감정 일기 앱 '오또'의 캐릭터 탄카츄다.
사용자와 영상통화로 오늘 있었던 일을 이야기한다. 너는 친한 친구처럼 들어주는 쪽이다.
[이번에 할 일]대로 탄카츄가 이어서 할 말 한마디만 쓴다.

[반응]
- 먼저 [방금 한 말]에 짧게 반응한다. 그 말에서 가장 마음이 담긴 부분을 받아준다.
- 사용자가 직접 말한 감정 단어는 그대로 되받아도 된다. 예: "부끄러웠어" → "아, 그렇게 부끄러웠군요."
- 반응은 매번 다르게 한다. 짧은 감탄("와", "헉", "아이고", "하하"), 들은 사실 되짚기("5분 넘게요."),
  반응 없이 바로 묻기 중에서 고른다. 매 차례 "~군요"로 받거나 "그럼"으로 질문을 시작하지 않는다.

[말투]
- 친구와 영상통화하듯 편한 존댓말. 소리로 듣는 말이라 두 문장 이내, 합쳐서 40자 안팎.
- 물음표는 한 번만. 직전에 탄카츄가 한 말과 같은 틀로 시작하지 않는다.
- 이런 말은 쓰지 않는다: "~하셨네요", "~라고 하셨는데", "더 이야기해줄 수 있어요?",
  "~에 대해 이야기해줄 수 있나요?", "~이 궁금해요"
- 호칭을 쓰지 않는다. 이모지를 쓰지 않는다.

[하지 않을 일]
- 사용자가 말하지 않은 감정을 짐작해 말하지 않는다. "~했겠어요", "~했겠네요", "힘들었겠어요",
  "속상하셨겠어요", "다행이었네요"처럼 감정을 덧붙이지 않는다. 감정 단어는 사용자가 먼저 말한 것만 쓴다.
- 기분을 물을 때 감정 단어를 먼저 제시하지 않는다. "속상했어요?"가 아니라 "그때 어땠어요?"처럼 묻는다.
- [이미 들은 것]은 다시 묻지 않는다. 사용자가 말하지 않은 내용을 지어내지 않는다.
- 방금 들은 시간·장소·사람을 그대로 되풀이하지 않는다.
  예: "오늘 오후 회사 회의실이요" → "오늘 오후 회사 회의실에서 어떤 일이 있었어요?"(X), "아, 회의실에서요."(O)
- 상담, 조언, 해석, 평가를 하지 않는다.
- 다툰 상대에 대해 물을 때 누가 옳은지 따지거나 상대 편을 들지 않는다. "그래도 상대도 사정이 있었겠죠"처럼
  사용자를 설득하지 않고, 상대가 한 말이나 상황을 사실로만 묻는다.

[대화 예시 — 다른 이야기다. 말투만 참고한다]
사용자: 오늘 동생이랑 마트 갔는데 지갑을 두고 와서 진짜 황당했어요.
탄카츄: 지갑을 두고 오다니, 진짜 황당했군요. 그래서 어떻게 했어요?
사용자: 결국 동생이 대신 냈어요. 웃으면서 다음에 맛있는 거 사라고 하더라고요.
탄카츄: 하하, 동생이 해결해줬네요. 마트엔 저녁에 간 거예요?
사용자: 네, 7시쯤이요.
탄카츄: 저녁 장 보러 갔다가 그랬군요. 지금 떠올리면 어때요?

[출력]
탄카츄가 할 말만 쓴다. 이름표나 따옴표를 붙이지 않는다."""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_REPLY_LABEL = re.compile(r"^(탄카츄|오또)\s*:\s*")

# 마무리 확인에 "더 없다"고 답한 것으로 보는 짧은 말 — LLM이 finished를 놓쳐도 끝낼 수 있게.
_NOTHING_MORE = re.compile(r"^(없|아니|괜찮|다\s*했|다\s*말했|끝|이게\s*다|그게\s*다)")
_NOTHING_MORE_MAX_LEN = 15

# 탄카츄가 직전에 기분을 물었는지 — 기분 질문이 연달아 나오지 않게.
_FEELING_QUESTION = re.compile(r"기분|마음|어땠|어때|느낌|느꼈|감정")

# 감정 짐작 어미("반가웠겠네요", "힘들었겠어요")와 문장 나누기.
_GUESS = re.compile(r"겠(어요|네요|군요|죠|다)")
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")
_LEADING_THEN = re.compile(r"^그럼\s*,?\s*")

# 말이 이어지는 어미로 끝난 발화("~했는데", "~하고") — 이때만 질문 없이 맞장구친다. LLM에게
# 맡기면 짧게 답을 마친 말도 이어가는 중으로 봐서 맞장구 차례가 너무 많아졌다.
# "회의실에서"의 "서"는 장소라 뺀다.
_TRAILING_OFF = re.compile(
    r"(는데|은데|던데|고|(?<!에)서|면서|지만|니까|거든|그리고|근데|그래서)[\s.,~…]*$"
)

# 감정 단어 줄기. 탄카츄 말에 사용자가 한 번도 말하지 않은 감정 단어가 있으면 짐작이다
# ("5분 넘게 안 되다니, 정말 난감했군요" — 사용자는 감정을 말하지 않았다).
_FEELING_WORDS = (
    "당황", "난감", "불편", "속상", "힘들", "힘드", "슬프", "슬펐", "기뻤", "기쁘", "화가", "화났",
    "짜증", "서운", "섭섭", "억울", "답답", "불안", "걱정", "초조", "창피", "부끄", "민망", "아쉬",
    "신나", "신났", "설레", "뿌듯", "행복", "우울", "외로", "무섭", "무서", "놀랐", "놀라", "황당",
    "다행", "미안", "편안", "편했", "상쾌", "즐거", "재밌", "재미있", "반가", "반갑", "실망", "괴로",
)


@dataclass
class InterviewTurn:
    reply: str
    done: bool
    # 칸 이름 → 채운 내용(빈 칸은 None). 칸을 알 수 없는 차례(LLM 실패)면 비어 있다.
    slots: dict[str, str | None] = field(default_factory=dict)
    # 지금까지 들은 이야기의 요약(보여주기용). 못 만든 차례면 None.
    summary: str | None = None
    # 누군가와 부딪힌 이야기인지 — 갈등 칸을 묻고 빈 칸으로 알릴지 정한다.
    conflict: bool = False

    @property
    def missing(self) -> list[str]:
        """빈 칸. 칸을 알 수 없으면 빈 목록 — 빈 칸이 없다는 뜻이 아니다.
        갈등이 아닌 날의 갈등 칸은 비어 있어도 빈 칸이 아니다."""
        if not self.slots:
            return []
        return [
            name
            for name in SLOTS
            if not self.slots.get(name) and (self.conflict or name not in CONFLICT_SLOTS)
        ]


@dataclass
class _Facts:
    """칸 추출 호출의 결과 — 말은 없고 판단만 있다."""

    slots: dict[str, str | None]
    summary: str | None
    just_felt: bool
    finished: bool
    conflict: bool = False


@dataclass
class _Plan:
    """서버가 고른 이번 차례의 할 일. kind: ask·listen·wrap·close"""

    kind: str
    targets: tuple[str, ...] = ()


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


def _last_oddo_text(history: Sequence[InterviewMessage]) -> str:
    for message in reversed(history):
        if message.speaker == "oddo":
            return message.text
    return ""


def _just_asked_wrap_up(history: Sequence[InterviewMessage]) -> bool:
    """이번 발화가 마무리 확인("더 하고 싶은 이야기")에 대한 답인지."""
    return WRAP_UP_MARK in _last_oddo_text(history)


def _says_nothing_more(user_text: str) -> bool:
    text = re.sub(r"[\s.!?~,]+$", "", user_text.strip())
    return len(text) <= _NOTHING_MORE_MAX_LEN and bool(_NOTHING_MORE.match(text))


_SPEAKER_LABEL = {"oddo": "탄카츄", "user": "사용자"}


def _dialogue(history: Sequence[InterviewMessage], user_text: str) -> list[str]:
    """대화를 역할별 메시지로 넘기면 모델이 대화체로 이어 말하며 지시를 무시한다
    (gpt-4o-mini에서 확인). 상담 리포트(counsel_report.py)처럼 대화를 한 요청에 담는다."""
    lines = ["[지금까지의 대화]"]
    lines += [f"{_SPEAKER_LABEL[m.speaker]}: {m.text}" for m in history]
    lines.append(f"사용자: {user_text}")
    lines.append(f"\n[방금 한 말] {user_text}")
    return lines


def _clean_slots(raw: object) -> dict[str, str | None]:
    values = raw if isinstance(raw, Mapping) else {}
    slots: dict[str, str | None] = {}
    for name in SLOTS:
        value = values.get(name)
        slots[name] = value.strip() if isinstance(value, str) and value.strip() else None
    return slots


def _extract(history: Sequence[InterviewMessage], user_text: str) -> _Facts:
    lines = _dialogue(history, user_text)
    lines.append("\n위 대화를 읽고 칸을 채운 뒤 지정한 JSON 형식으로만 답한다.")
    raw = llm_client.chat(
        EXTRACT_PROMPT,
        [{"role": "user", "content": "\n".join(lines)}],
        temperature=0,
        max_tokens=500,
        json_mode=True,
    )
    data = json.loads(_FENCE.sub("", raw.strip()).strip())
    if not isinstance(data, Mapping):
        raise ValueError("extraction must be a JSON object")
    summary = data.get("summary")
    return _Facts(
        slots=_clean_slots(data.get("slots")),
        summary=summary.strip() if isinstance(summary, str) and summary.strip() else None,
        just_felt=data.get("just_felt") is True,
        finished=data.get("finished") is True,
        conflict=data.get("conflict") is True,
    )


def _plan(
    facts: _Facts, history: Sequence[InterviewMessage], user_text: str, remaining: int
) -> _Plan:
    missing = [
        n
        for n in SLOTS
        if not facts.slots.get(n)
        and n not in OPTIONAL_SLOTS
        and (facts.conflict or n not in CONFLICT_SLOTS)
    ]
    last = _last_oddo_text(history)
    # 맞장구만 하는 차례는 연달아 하면 대화가 멈춘 것처럼 들려서, 직전에 물었을 때만 둔다.
    may_listen = bool(_TRAILING_OFF.search(user_text.strip())) and "?" in last
    wrapping_up = _just_asked_wrap_up(history)

    if remaining == 0 or (wrapping_up and (facts.finished or _says_nothing_more(user_text))):
        return _Plan("close")
    if not missing:
        # 칸이 다 찼으면 끝내기 전에 더 하고 싶은 이야기가 있는지 묻는다. 이야기를 이어가는
        # 중이면 들어주고, 질문이 한 번밖에 안 남았으면 바로 확인한다.
        if may_listen and remaining > 1:
            return _Plan("listen")
        return _Plan("wrap")
    if may_listen:
        return _Plan("listen")
    # 방금 감정을 말했거나 직전에 기분을 물었으면 기분은 이번에 묻지 않는다.
    skip_feelings = facts.just_felt or ("?" in last and bool(_FEELING_QUESTION.search(last)))
    order = [name for name in ASK_ORDER if name in missing]
    candidates = [n for n in order if not (skip_feelings and n in FEELING_SLOTS)]
    if not candidates:
        # 남은 게 기분 칸뿐인데 지금은 물을 때가 아니다 — 들어주고 다음 차례에 묻는다.
        if "?" in last:
            return _Plan("listen")
        candidates = order
    return _Plan("ask", tuple(candidates[:2]))


def _task(plan: _Plan) -> str:
    if plan.kind == "ask":
        # 칸 설명("일이 어떻게 흘러갔는지")을 주면 그대로 베껴 묻는다 — 묻는 말 예시만 준다.
        names = "\n".join(f"- {name}: 묻는 말 예 \"{SLOT_QUESTIONS[name]}\"" for name in plan.targets)
        feeling = any(name in FEELING_SLOTS for name in plan.targets)
        other = any(name in CONFLICT_SLOTS for name in plan.targets)
        return (
            f"짧게 반응한 뒤, 다음 중 이야기 흐름에 맞는 하나를 이야기에 맞춰 묻는다.\n{names}"
            + ("\n기분을 묻는다면 그 순간을 콕 집어, 감정 단어 없이 묻는다." if feeling else "")
            + ("\n상대에 대해 묻는다면 누가 옳은지 따지지 않고 사실만 묻는다." if other else "")
        )
    if plan.kind == "listen":
        return "질문하지 않는다. 짧게 맞장구치며 이어서 들려달라고 한다. 물음표를 쓰지 않는다."
    return f'짧게 반응한 뒤 "{WRAP_UP_MARK}"가 있는지 묻는다. "{WRAP_UP_MARK}"라는 구절을 꼭 넣는다.'


def _compose(history: Sequence[InterviewMessage], user_text: str, facts: _Facts, plan: _Plan) -> str:
    heard = [f"- {name}: {value}" for name, value in facts.slots.items() if value]
    lines = _dialogue(history, user_text)
    lines.append("\n[이미 들은 것]")
    lines += heard or ["- 아직 없음"]
    lines.append(f"\n[이번에 할 일] {_task(plan)}")
    raw = llm_client.chat(
        REPLY_PROMPT,
        [{"role": "user", "content": "\n".join(lines)}],
        temperature=0.7,
        max_tokens=120,
    )
    reply = _REPLY_LABEL.sub("", raw.strip()).strip().strip('"')
    if not reply:
        raise ValueError("reply must be a non-empty string")
    return reply


def _guesses_feeling(sentence: str, user_said: str) -> bool:
    if "?" not in sentence and _GUESS.search(sentence):
        return True
    return any(word in sentence and word not in user_said for word in _FEELING_WORDS)


def _tidy(reply: str, user_said: str) -> str:
    """프롬프트로 막아도 gpt-4o-mini가 되풀이하는 말버릇을 서버에서 정리한다.

    - 사용자가 말하지 않은 감정을 덧붙인 문장("~했겠어요", "정말 난감했군요")은 뺀다 — 그 감정
      단어를 사용자가 따라 말하면 분석이 끌려간다. 감정 단어를 넣은 질문("속상했어요?")도 뺀다.
    - 매 질문을 "그럼"으로 시작하면 설문처럼 들려서 뗀다.
    """
    sentences = [s.strip() for s in _SENTENCE.findall(reply) if s.strip()]
    kept = [_LEADING_THEN.sub("", s) for s in sentences if not _guesses_feeling(s, user_said)]
    return " ".join(s for s in kept if s)


def _guard(reply: str, plan: _Plan, user_said: str) -> str:
    """말이 할 일을 어기면 고정 문구로 — 맞장구인데 묻거나, 물어야 하는데 안 묻거나."""
    reply = _tidy(reply, user_said)
    if plan.kind == "listen":
        # 맞장구 차례엔 빈 칸을 알려주지 않아서, 여기서 나온 질문은 엉뚱하거나 들은 걸 되묻는다.
        reply = " ".join(s.strip() for s in _SENTENCE.findall(reply) if s.strip() and "?" not in s)
    if not reply:
        return _fixed_line(plan)
    if plan.kind == "wrap" and WRAP_UP_MARK not in reply:
        return WRAP_UP
    if plan.kind == "ask" and "?" not in reply:
        return SLOT_QUESTIONS[plan.targets[0]]
    return reply


def _fixed_line(plan: _Plan) -> str:
    return {
        "ask": lambda: SLOT_QUESTIONS[plan.targets[0]],
        "listen": lambda: random.choice(LISTENINGS),
        "wrap": lambda: WRAP_UP,
        "close": lambda: random.choice(CLOSINGS),
    }[plan.kind]()


def _fallback(asked: int, remaining: int, wrapping_up: bool) -> InterviewTurn:
    if remaining > 0 and not wrapping_up and asked < len(FALLBACK_QUESTIONS):
        return InterviewTurn(reply=FALLBACK_QUESTIONS[asked], done=False)
    return InterviewTurn(reply=random.choice(CLOSINGS), done=True)


def next_turn(history: Sequence[InterviewMessage], user_text: str) -> InterviewTurn:
    asked = follow_ups_asked(history)
    remaining = max(MAX_FOLLOW_UPS - asked, 0)
    try:
        facts = _extract(history, user_text)
    except Exception as exc:
        # 키 미설정·네트워크 오류·JSON 형식 오류 — 대화가 멈추지 않도록 고정 문구로.
        # 사용자 발화는 로그에 남기지 않는다.
        logger.warning("diary interview fell back to a fixed line: %s", type(exc).__name__)
        return _fallback(asked, remaining, _just_asked_wrap_up(history))

    if facts.conflict:
        remaining = max(MAX_FOLLOW_UPS + CONFLICT_EXTRA_FOLLOW_UPS - asked, 0)
    plan = _plan(facts, history, user_text, remaining)
    user_said = " ".join([*(m.text for m in history if m.speaker == "user"), user_text])
    try:
        # 끝인사는 고정 문구라 말 만들기를 부르지 않는다.
        reply = (
            _fixed_line(plan)
            if plan.kind == "close"
            else _guard(_compose(history, user_text, facts, plan), plan, user_said)
        )
    except Exception as exc:
        # 칸은 알았으니 할 일에 맞는 고정 문구로 잇는다.
        logger.warning("diary interview reply fell back to a fixed line: %s", type(exc).__name__)
        reply = _fixed_line(plan)
    return InterviewTurn(
        reply=reply,
        done=plan.kind == "close",
        slots=facts.slots,
        summary=facts.summary,
        conflict=facts.conflict,
    )
