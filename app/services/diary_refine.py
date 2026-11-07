"""일기 대화 → 일기 한 편 정제 (39번 확인 화면의 "오늘의 일기").

팀 결정: 탄카츄와 나눈 대화를 일기 한 편으로 정제해 보여주고, 원래 대화는 "대화 내용
보기"로 따로 보여준다. 정제본은 **보여주기용**이다 — 감정 분석·영상 입력은 사용자 답변
원문을 그대로 쓴다(LLM이 다듬은 글을 넣으면 텍스트 감정이 달라진다).

정제 규칙의 앞 네 줄은 팀이 합의한 문장 그대로다. 나머지는 대화 형식이라 필요한 보강이다
(질문에 대한 짧은 답은 질문 없이는 뜻이 안 통한다).

바로 일기를 쓰게 하면 답변을 하나씩 평문으로만 옮겨서 같은 내용이 반복된다(#104). 그래서
모델이 facts·feelings로 말한 내용을 중복 없이 뽑은 뒤 그걸 전부 써서 diary를 만들게 한다.
두 칸은 모델이 내용을 정리하는 자리라 앱에는 내려보내지 않는다.

그렇게 쓴 초안은 말을 받아 적은 문장 구조가 남아 있어서 POLISH_PROMPT로 한 번 더 글로
다듬는다. 이때 서버가 찾은 문제(빠진 감정·되풀이·말투 끝·말하지 않은 감정)도 함께 고치게
한다. 다듬다가 내용이 줄거나 문제가 늘면 초안을 쓴다. 재료만 주고 새로 쓰게 하는 방식은
없는 감정을 지어내서 쓰지 않는다 — 다듬기 단계도 항상 초안을 보고 고친다.

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

[쓰는 순서]
답변을 차례대로 옮겨 적지 않는다. 답변 하나가 문장 하나가 되면 안 된다.
1. facts: 답변을 처음부터 끝까지 읽으며 사용자가 말한 사실을 하나씩 짧게 적는다. 이미 적은 사실이 또 나오면
   새로 적지 않고, 더 구체적으로 말했으면 그 표현으로 고친다. 숫자, 누가 한 말, 몸의 반응은 표현 그대로 둔다.
2. feelings: 사용자가 쓴 감정 표현을 쓴 단어 그대로 하나씩 적는다. 같은 단어는 한 번만 적는다.
3. diary: facts와 feelings를 하나도 빼지 말고 일이 일어난 순서대로 풀어 일기 한 편으로 쓴다. 1~3문단.

[같은 내용 합치기]
- 요약하지 않는다. 서로 다른 사실과 감정은 빠뜨리지 않는다. 다만 같은 내용을 다시 말한 것은 한 번만 쓴다.
  가장 구체적으로 말한 쪽을 남긴다. 되풀이를 뺀 것 말고는 내용을 줄이지 않는다.
- 같은 일에 대한 감정을 여러 답에서 말했으면 단어를 한 문장에 모은다
  (예: "당황스러웠어" / "많이 부끄러웠어" / "너무 부끄러웠어" → "당황스럽고 너무 부끄러웠다").
  같은 감정 단어는 서로 다른 일에 대한 감정일 때만 다시 쓴다.
- 시간·장소·이유만 말한 답은 따로 문장으로 두지 않고 그 일을 쓰는 문장 안에 넣는다
  (예: "회의에서 자료가 안 열렸어" / "회사 회의실이었어" → "회사 회의실에서 회의를 하는데 자료가 안 열렸다").
- 서로 다른 것을 짐작으로 같은 것으로 합치지 않는다(예: "맛집"과 "떡볶이 집"이 같은 곳이라고 말하지 않았다면 따로 쓴다).

[군더더기]
- 말버릇은 뺀다: 그냥, 뭐, 막, 뭔가, 이제, 그러니까, 아무래도, 있잖아, 음, 어.
  (예: "그냥 뭐 착잡하고 답답했지" → "착잡하고 답답했다")
- 감정의 세기를 나타내는 말은 남긴다: 너무, 진짜, 정말, 많이, 조금, 좀, 약간.
- 말하다가 바로잡은 부분("어제… 아니 오늘")은 바로잡은 쪽만 쓴다.
- "없어요"처럼 대화를 마무리하는 답, 인사말은 넣지 않는다.

[일기체]
- 일기체(~했다)로 쓴다. 문장 끝에 말하는 투를 남기지 않는다
  (예: "있더라고" → "있었다", "화를 내는 거야" → "화를 냈다", "그랬거든" → "그랬다", "좋았지" → "좋았다").
- 감정 표현은 단어를 바꾸지 않고 끝만 맞춘다(예: "속상했어요" → "속상했다").
- 1인칭도 일기체에 맞춰 "저/제가/제"를 "나/내가/내"로 쓴다.

[맥락]
- 탄카츄의 질문과 말은 넣지 않는다. 짧은 답은 질문의 맥락을 살려 알맞은 문장에 넣는다.
- 기분만 말한 답은 그 기분이 든 일과 이어서 쓴다. 어떤 일에 대한 기분인지는 질문과 앞뒤 답으로 판단하고,
  분명하지 않으면 이유를 지어 붙이지 말고 그대로 쓴다.
- 사용자가 잇지 않은 두 일을 원인과 결과로 잇지 않는다("~해서"를 새로 만들지 않는다).
- 망설임이나 추측("~싶기도 하다", "~것 같다")은 단정으로 바꾸지 않는다.
- 사람 이름·장소 같은 고유명사는 그대로 쓴다. 음성 인식이 틀린 것 같은 말도 짐작으로 고치지 않는다.

[예시]
탄카츄: 오늘 어떤 일이 있었는지 이야기해줄래요?
사용자: 아침에 버스에 지갑을 두고 내렸어
탄카츄: 저런, 그래서 어떻게 됐어요?
사용자: 그냥 뭐 지갑을 놓고 내린 거지 그래서 버스 회사에 전화했어
탄카츄: 그 순간엔 마음이 어땠어요?
사용자: 막 식은땀 나고 너무 당황했지
탄카츄: 어디서 내렸어요?
사용자: 학교 앞이요
탄카츄: 지금은 좀 어때요?
사용자: 저녁에 기사님이 찾아주셔서 받았거든 이제 안심돼
탄카츄: 오늘 더 하고 싶은 이야기 있어요?
사용자: 아니 없어

{"facts": ["아침에 학교 앞에서 버스에 지갑을 두고 내림", "식은땀이 남", "버스 회사에 전화함", "저녁에 기사님이 찾아주셔서 지갑을 받음"],
 "feelings": ["너무 당황", "안심"],
 "diary": "아침에 학교 앞에서 버스에 지갑을 두고 내렸다. 식은땀이 나고 너무 당황했다. 버스 회사에 전화했고, 저녁에 기사님이 찾아주셔서 지갑을 받았다. 지금은 안심된다."}

[출력]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{"facts": ["사실"], "feelings": ["감정 표현"], "diary": "정리한 일기"}"""

POLISH_PROMPT = """너는 말을 받아 적은 일기 [초안]을 사람이 일기장에 직접 쓴 글처럼 다듬는 편집자다.

[지킬 것]
- 내용은 그대로 둔다. 사실·감정·생각을 더하지도 빼지도 않는다. 초안에 없는 감정이나 이유를 넣지 않는다.
- 감정 단어는 바꾸지 않고 활용만 맞춘다(예: "부럽고" → "부러웠다").
- 망설임이나 추측("~싶기도 하다", "~것 같다")은 단정으로 바꾸지 않는다.
- 사람 이름·장소 같은 고유명사와 음성 인식이 틀린 것 같은 말은 고치지 않는다.

[다듬을 것]
- 말할 때 쓰는 문장 구조를 글의 구조로 바꾼다.
  어색: "시험공부도 막막하고 잘하는 친구들 부럽고 했다." → 자연: "시험공부는 막막했고, 잘하는 친구들이 부러웠다."
  어색: "날씨가 추우니까 감기 걸린 거고 다른 이유는 딱히 없다." → 자연: "날씨가 추워서 감기에 걸렸을 뿐, 다른 이유는 없었다."
  어색: "잘 모르겠더라." → 자연: "잘 몰랐다."
- 쉼표나 "~고"로 길게 이은 문장은 나눈다.
- 그냥·뭐·막·뭔가·아무래도 같은 말버릇을 뺀다.
- 같은 내용이나 같은 감정을 되풀이한 곳은 하나로 합친다.
- 모든 문장은 일기체(~했다)로 끝낸다.
- 빠진 감정은 감정 단어만 골라 그 일을 쓴 문장 안에 넣는다. 사용자가 한 말을 문장째 옮겨 붙이지 않는다.
- [꼭 고칠 것]이 있으면 반드시 고친다.

[출력]
JSON만 출력한다. 설명을 덧붙이지 않는다.
{"diary": "다듬은 일기 전체"}"""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_SPEAKER_LABEL = {"oddo": "탄카츄", "user": "사용자"}
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")
_REPEAT_OVERLAP = 0.6
_MIN_CLAUSE_BIGRAMS = 8  # 이보다 짧은 절은 우연히 겹치기 쉽다.
_MIN_POLISHED_RATIO = 0.7  # 다듬은 글이 이보다 짧아지면 내용까지 줄인 것으로 본다.

# 같은 감정의 활용형을 한 정규식으로 묶는다("슬펐어"를 "슬프고"로 쓴 건 빠뜨린 게 아니다).
# "화"는 전화·영화·대화에, "부러"는 일부러에 걸리지 않게 앞 글자를 본다.
_FEELINGS = tuple(
    re.compile(pattern)
    for pattern in (
        "당황", "난감", "불편", "속상", "짜증", "서운", "섭섭", "억울", "답답", "불안", "걱정", "초조",
        "창피", "부끄", "민망", "아쉬", "설레", "뿌듯", "행복", "우울", "외로", "황당", "다행", "미안",
        "상쾌", "즐거", "실망", "괴로", "착잡", "어이없", "조마조마", "후련", "막막", "죄송", "안심",
        "긴장", "조급", "스트레스", "힐링", "귀찮", "허탈", "허무", "심란", "찝찝", "씁쓸", "감동", "기대",
        "슬프|슬펐", "기쁘|기뻤", "마음이 아프|마음이 아팠", "(?<![가-힣])화(?:가|났|를)", "힘들|힘드",
        "고맙|고마", "부럽|(?<!일)부러", "무섭|무서", "놀라|놀랐", "반갑|반가", "신나|신났",
        "편안|편했|편하", "재밌|재미있", "두렵|두려",
    )
)


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


def _ask(system_prompt: str, content: str) -> str:
    return llm_client.chat(
        system_prompt,
        [{"role": "user", "content": content}],
        temperature=0.3,
        max_tokens=2500,  # facts·feelings까지 함께 나오므로 일기 길이보다 넉넉하게 둔다.
        json_mode=True,
    )


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


def _bigrams(sentence: str) -> set[str]:
    letters = re.sub(r"[^가-힣0-9]", "", sentence)
    return {letters[i : i + 2] for i in range(len(letters) - 1)}


def _repeated_sentences(diary: str) -> list[tuple[str, str]]:
    """글자가 거의 겹치는 문장 쌍. 쉼표로 나눠 문장 일부만 되풀이한 것까지 잡는다."""
    clauses = [
        (sentence, grams)
        for sentence in _sentences(diary)
        for clause in sentence.split(",")
        if len(grams := _bigrams(clause)) >= _MIN_CLAUSE_BIGRAMS
    ]
    pairs = [
        (a, b)
        for i, (a, grams_a) in enumerate(clauses)
        for b, grams_b in clauses[i + 1 :]
        if a != b and len(grams_a & grams_b) / min(len(grams_a), len(grams_b)) >= _REPEAT_OVERLAP
    ]
    return list(dict.fromkeys(pairs))


def _spoken_sentences(diary: str) -> list[str]:
    return [s for s in _sentences(diary) if not s.rstrip(".!?…").endswith("다")]


def _missing_feelings(diary: str, user_said: str) -> list[tuple[str, str]]:
    """일기에 없는 감정과 그 감정을 말한 문장."""
    missing = []
    for feeling in _FEELINGS:
        if feeling.search(diary):
            continue
        said = next((s for s in _sentences(user_said) if feeling.search(s)), None)
        if said:
            missing.append((feeling.search(said).group(), said))
    return missing


def _invented_feelings(diary: str, user_said: str) -> list[str]:
    return [
        found.group()
        for feeling in _FEELINGS
        if (found := feeling.search(diary)) and not feeling.search(user_said)
    ]


def _problems(diary: str, user_said: str) -> list[str]:
    """모델이 facts·feelings에 적고도 일기에서 놓치는 것을 서버가 찾는다."""
    problems = [
        f'- 사용자가 "{said}"라고 말했는데 "{word}" 표현이 일기에 없다. 알맞은 문장에 넣는다.'
        for word, said in _missing_feelings(diary, user_said)
    ]
    problems += [
        f'- 같은 내용이 되풀이됐다. 한 문장으로 합친다: "{a}" / "{b}"'
        for a, b in _repeated_sentences(diary)
    ]
    problems += [f'- 말하는 투로 끝났다. 일기체(~했다)로 고친다: "{s}"' for s in _spoken_sentences(diary)]
    problems += [f'- 사용자가 말하지 않은 감정 "{word}"을 뺀다.' for word in _invented_feelings(diary, user_said)]
    return problems


def _polish(diary: str, user_said: str) -> str:
    """초안을 글로 다듬는다. 내용이 줄거나 문제가 늘면 다듬기 전 초안을 그대로 둔다."""
    problems = _problems(diary, user_said)
    lines = ["[초안]", diary]
    if problems:
        lines += ["", "[꼭 고칠 것]", *problems]
    try:
        polished = _parse(_ask(POLISH_PROMPT, "\n".join(lines)))
    except Exception as exc:
        logger.warning("diary polish failed: %s", type(exc).__name__)
        return diary
    if len(polished) < len(diary) * _MIN_POLISHED_RATIO:
        return diary
    return polished if len(_problems(polished, user_said)) <= len(problems) else diary


def refine_diary(messages: Sequence[InterviewMessage]) -> str | None:
    try:
        diary = _parse(_ask(SYSTEM_PROMPT, _build_user_prompt(messages)))
    except Exception as exc:
        # 키 미설정·네트워크 오류·JSON 형식 오류 — 앱이 원 답변을 보여준다.
        # 사용자 발화는 로그에 남기지 않는다.
        logger.warning("diary refine failed: %s", type(exc).__name__)
        return None
    return _polish(diary, " ".join(m.text for m in messages if m.speaker == "user"))
