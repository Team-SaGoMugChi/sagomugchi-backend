"""상담 SFT 학습 데이터 생성기.

`app/services/counsel_prompt.py`의 시스템 프롬프트를 그대로 써서, 그 규칙을
따르는 상담 대화를 GPT-4o에게 쓰게 한다. 사람이 검수한 뒤 학습에 쓴다.
공개 감정대화 말뭉치(AI Hub 등)는 영리 이용 제한이 있어 쓰지 않는다.

한 대화는 상담봇의 인사로 시작한다. 실제 앱에서도 baseline·일기·감정 분석
결과를 들고 상담봇이 먼저 말을 걸기 때문이다.

사용법:
    python scripts/generate_sft_data.py --count 20 --out data/sft/generated.jsonl

출력은 OpenAI 파인튜닝 형식(JSONL). 한 줄 = 대화 하나.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.counsel_prompt import build_system_prompt  # noqa: E402

# 상황 하나가 곧 하나의 맥락 묶음이다. 실제 앱이 상담봇에게 넘기는 값과 같은
# 모양으로 만들어야, 학습한 모델이 서비스에서도 같은 재료를 받는다.
SCENARIOS = [
    {
        "diary_summary": "팀플 발표를 맡았는데 준비한 내용이 잘 전달되지 않았다고 적음",
        "emotions": {"당황": 68.0, "슬픔": 55.0, "불안": 40.0},
        "signals": ["말 속도가 평소보다 빠름", "목소리 떨림이 늘어남"],
        "recent_themes": ["자기 비난"],
    },
    {
        "diary_summary": "팀 과제에서 대부분의 작업을 혼자 맡게 되었다고 적음",
        "emotions": {"분노": 64.0, "억울함": 58.0, "피로": 45.0},
        "signals": ["목소리 세기가 평소보다 큼"],
        "recent_themes": [],
    },
    {
        "diary_summary": "야근이 이어졌지만 회사에서는 괜찮은 척했다고 적음",
        "emotions": {"피로": 75.0, "무기력": 50.0},
        "signals": ["말 속도가 평소보다 느림", "표정 변화가 적음"],
        "recent_themes": ["수면 부족"],
    },
    {
        "diary_summary": "친구가 한 말이 서운했지만 그 자리에서 말하지 못했다고 적음",
        "emotions": {"서운함": 70.0, "슬픔": 42.0},
        "signals": ["문장 끝 목소리가 낮아짐"],
        "recent_themes": ["관계에서 참기"],
    },
    {
        "diary_summary": "시험 결과가 기대보다 나빴고 준비가 부족했다고 적음",
        "emotions": {"실망": 66.0, "불안": 48.0},
        "signals": [],
        "recent_themes": ["자기 비난"],
    },
    {
        "diary_summary": "취업 준비가 길어져 지친다고 적음",
        "emotions": {"무기력": 72.0, "불안": 55.0},
        "signals": ["말 속도가 평소보다 느림"],
        "recent_themes": ["끝이 안 보인다는 생각"],
    },
    {
        "diary_summary": "가족과 사소한 일로 다퉜고 지나고 나니 후회된다고 적음",
        "emotions": {"후회": 62.0, "분노": 38.0},
        "signals": [],
        "recent_themes": [],
    },
    {
        "diary_summary": "특별한 일은 없었는데 하루 종일 기분이 가라앉았다고 적음",
        "emotions": {"우울감": 58.0, "무기력": 52.0},
        "signals": ["표정 변화가 적음", "발화량이 평소보다 적음"],
        "recent_themes": ["이유 없는 가라앉음"],
    },
    {
        "diary_summary": "칭찬을 받았는데도 마음이 놓이지 않았다고 적음",
        "emotions": {"불안": 60.0, "기쁨": 35.0},
        "signals": [],
        "recent_themes": ["잘해야 한다는 부담"],
    },
    {
        "diary_summary": "새 환경에 적응이 안 돼 겉도는 느낌이라고 적음",
        "emotions": {"외로움": 64.0, "불안": 44.0},
        "signals": ["발화량이 평소보다 적음"],
        "recent_themes": [],
    },
    {
        "diary_summary": "오랜만에 쉬었는데 오히려 허전했다고 적음",
        "emotions": {"공허함": 55.0, "피로": 40.0},
        "signals": [],
        "recent_themes": [],
    },
    {
        "diary_summary": "준비하던 일이 잘 풀려서 기분이 좋았다고 적음",
        "emotions": {"기쁨": 78.0, "뿌듯함": 60.0},
        "signals": ["목소리 높이가 평소보다 높음"],
        "recent_themes": [],
    },
]

# 사용자가 어떻게 말하는지. 앱에서 실제로 마주칠 유형을 고르게 섞는다.
USER_STYLES = [
    ("자기 상황을 비교적 잘 설명하는", ""),
    ("짧게 단답으로만 답하는", "상담봇은 [말이 잘 안 나올 때] 사다리를 위에서부터 사용한다."),
    (
        "무슨 감정인지 스스로도 모르겠다고 말하는",
        "상담봇은 선택지·척도·몸의 감각 질문을 차례로 써서 감정에 이름을 붙이도록 돕는다.",
    ),
    (
        "괜찮다고 하면서 속내를 숨기는",
        "상담봇은 한 번만 조심스럽게 신호 차이를 짚고, 아니라고 하면 더 캐묻지 않는다.",
    ),
    ("말이 많고 감정을 쏟아내는", "상담봇은 중간에 한 번 요약해서 핵심을 정리한다."),
]

# 마무리 방식을 섞어야 "항상 행동 제안으로 끝내는" 습관을 배우지 않는다.
ENDINGS = [
    "마지막 응답은 오늘 이야기를 한 문장으로 정리하고 끝낸다. 제안도 질문도 하지 않는다.",
    "마지막 응답은 사용자가 스스로 알아차린 점을 짚어주고 끝낸다.",
    "마지막 응답은 호흡·산책·메모처럼 아주 작은 행동을 하나만 제안하고 끝낸다.",
    "마지막 응답은 지금은 답을 내지 않아도 된다고 말하며 끝낸다.",
    "마지막 응답은 작은 실험을 제안한다. 예: 그 생각이 들 때 메모해두고 나중에 다시 읽어보기.",
]

WRITER_PROMPT = """아래 시스템 프롬프트를 지키는 상담봇과 사용자의 대화를 만든다.
너는 학습 데이터를 만드는 작가이고, 상담봇 응답은 이 프롬프트를 그대로 따라야 한다.

=== 상담봇 시스템 프롬프트 ===
{system_prompt}
=== 끝 ===

[오늘 사용자가 겪은 일] {diary}
[사용자 말투] {style}
{style_note}
[마무리 방식] {ending}

작성 규칙:
- 상담봇이 먼저 인사하며 시작한다. 첫 응답은 위 맥락을 활용해 답하기 쉬운
  질문 하나를 던진다. 분석 수치나 라벨을 그대로 읽어주지 않는다.
- 상담봇 5번, 사용자 4번을 번갈아 쓴다. 상담봇 응답으로 끝난다.
- 상담봇 응답은 2~3문장, 물음표는 응답당 최대 한 번.
- 호칭('~님', '당신', '너', '사용자')을 응답에 쓰지 않는다.
- CBT 사고기록 순서(상황 → 감정 → 자동적 사고 → 근거 → 대안)를 따라가되,
  사용자가 아직 감정을 풀어놓는 중이면 다음 단계로 넘어가지 않는다.
- 사용자가 분석과 다른 감정을 말하면 상담봇은 사용자의 말을 따른다.
- 진단명·약·"괜찮아질 거예요" 같은 근거 없는 위로는 쓰지 않는다.
- 자해·자살 관련 내용은 넣지 않는다(앱에서 따로 처리한다).

출력은 JSON만. 형식:
{{"turns": [{{"speaker": "oddo", "text": "..."}}, {{"speaker": "user", "text": "..."}}, ...]}}"""

# 검수 전에 기계적으로 거를 수 있는 것들.
BANNED = ("괜찮아질", "진단", "우울증", "불안장애", "약을 드시", "처방", "별일 아니")
HONORIFICS = ("님", "당신", "사용자")
SCORE_PATTERN = re.compile(r"\d+\s*(점|%)")


def is_clean(messages: list[dict]) -> bool:
    """프롬프트 규칙을 눈에 띄게 어긴 대화를 걸러낸다."""
    for m in messages:
        if m["role"] != "assistant":
            continue
        text = m["content"]
        if text.count("?") > 1:
            return False
        if len(text) > 160:
            return False
        if SCORE_PATTERN.search(text):  # "슬픔 72점" 같은 수치 낭독
            return False
        if any(word in text for word in BANNED):
            return False
        if any(word in text for word in HONORIFICS):
            return False
    return True


def generate_one(
    client: OpenAI,
    model: str,
    scenario: dict,
    style: tuple[str, str],
    ending: str,
) -> dict | None:
    # 서비스에서 쓰는 프롬프트를 그대로 만들어, 그 안에서 대화를 쓰게 한다.
    system_prompt = build_system_prompt(
        emotions=scenario["emotions"],
        signals=scenario["signals"] or None,
        diary_summary=scenario["diary_summary"],
        recent_themes=scenario["recent_themes"] or None,
        incongruent=style[0] == "괜찮다고 하면서 속내를 숨기는",
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": WRITER_PROMPT.format(
                    system_prompt=system_prompt,
                    diary=scenario["diary_summary"],
                    style=style[0],
                    style_note=style[1],
                    ending=ending,
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=1.0,
    )
    try:
        turns = json.loads(response.choices[0].message.content)["turns"]
    except (KeyError, ValueError):
        return None

    messages = [{"role": "system", "content": system_prompt}]
    for turn in turns:
        role = "assistant" if turn.get("speaker") == "oddo" else "user"
        text = (turn.get("text") or "").strip()
        if not text:
            return None
        messages.append({"role": role, "content": text})

    # 상담봇 인사로 시작해 상담봇 응답으로 끝나야 한다.
    if len(messages) < 7:
        return None
    if messages[1]["role"] != "assistant" or messages[-1]["role"] != "assistant":
        return None
    if not is_clean(messages):
        return None
    return {"messages": messages}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="생성할 대화 수")
    parser.add_argument("--out", default="data/sft/generated.jsonl")
    parser.add_argument("--model", default="gpt-4o", help="데이터를 쓰는 모델")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit(".env의 LLM_API_KEY가 비어 있습니다.")

    client = OpenAI(api_key=settings.llm_api_key)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(args.count):
            scenario = SCENARIOS[i % len(SCENARIOS)]
            style = USER_STYLES[i % len(USER_STYLES)]
            ending = random.choice(ENDINGS)
            sample = generate_one(client, args.model, scenario, style, ending)
            if sample is None:
                print(f"[{i + 1}/{args.count}] 규칙 위반 — 건너뜀")
                continue
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            written += 1
            print(f"[{i + 1}/{args.count}] {scenario['diary_summary'][:20]}… 저장")

    print(f"\n{written}개 저장 → {out_path}")
    print("검수 후 학습에 쓰세요. 검수 기준은 data/sft/README.md 참고.")


if __name__ == "__main__":
    main()