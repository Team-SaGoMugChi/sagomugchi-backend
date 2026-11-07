"""CBT 단계형 상담 SFT 데이터 생성기 — 서비스와 같은 흐름으로 상담 회기를 만든다.

왜 새로 만드나
    generate_sft_data.py는 상담봇이 문장으로 답하는 자유 대화를 만든다. 앱의 CBT
    단계형 상담은 상담봇이 매 턴 JSON({"reply", "advance", "extracted"})으로 답하고,
    단계마다 시스템 프롬프트가 바뀐다. 그 데이터로 학습한 모델은 CBT 모드에서 쓸 수 없다.

흐름 (/counsel/turn CBT 경로와 같다)
    사용자 시뮬레이터(LLM) 발화 → 위기 판정(assess) → build_system_prompt + build_cbt_prompt
    → 상담봇(LLM, JSON) → 응답 검증(check_reply)·extracted 키 검사 → next_state로 다음 단계

    한 회기를 5단계가 끝날 때까지 진행해 회기 단위로 저장한다.
    학습용 턴 단위 변환은 prepare_cbt_sft_data.py가 한다.

사용법
    python -X utf8 scripts/generate_cbt_sft_data.py --count 5             # 먼저 소량으로 비용 확인
    python -X utf8 scripts/generate_cbt_sft_data.py --count 60 --seed 1   # 이어서 실행하면 덧붙는다

출력: data/sft/cbt_sessions.jsonl (한 줄 = 회기 하나, .gitignore 대상)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services import counsel_cbt, llm_client  # noqa: E402
from app.services.counsel_guardrail import RiskLevel, assess  # noqa: E402
from app.services.counsel_output_check import (  # noqa: E402
    HARD,
    check_reply,
    feedback_for,
    repair,
)
from app.services.counsel_prompt import build_system_prompt  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "sft" / "cbt_sessions.jsonl"

# 단계별로 extracted에 들어올 수 있는 키 (counsel_cbt._STAGE_PROMPTS와 같다).
STAGE_KEYS: dict[int, set[str]] = {
    0: {"missionDone", "missionFeedback"},
    1: {"emotionLabel", "intensity"},
    2: {"situation", "automaticThought"},
    3: {"insight", "beliefBefore"},
    4: {"evidenceFor", "evidenceAgainst", "alternativeThought", "beliefAfter"},
    5: {"mission", "sessionSummary"},
}

# /counsel/turn의 CBT 턴과 같은 값.
BOT_MAX_TOKENS = 600
# 한 회기 최대 턴. 단계마다 최대 3턴(MAX_STAGE_TURNS) × 6단계 = 18.
MAX_TURNS = 20
# 규칙을 어긴 응답을 다시 받는 횟수. 그래도 어기면 회기를 거기서 끝낸다.
BOT_RETRIES = 2

# 앱이 상담봇에게 넘기는 값과 같은 모양의 맥락.
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
        "emotions": {"슬픔": 58.0, "무기력": 52.0},
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
    "자기 상황을 비교적 잘 설명한다",
    "짧게 단답으로만 답한다",
    "무슨 감정인지 스스로도 잘 모르겠다고 한다",
    "괜찮다고 하면서 속내를 잘 드러내지 않는다",
    "말이 많고 감정을 쏟아낸다",
]

# 앱의 챗봇 말투(persona.tone)와 상담 스타일(CounselCbtState.styleForTone)을 같이 맞춘다.
PERSONAS = [
    ({"name": "오디", "tone": "친근하고 따뜻한", "traits": ["공감 잘해주는"]}, "empathy"),
    ({"name": "오디", "tone": "차분하고 진중한", "traits": ["신중한"]}, "analysis"),
    ({"name": "오디", "tone": "간결하고 솔직한", "traits": ["솔직한"]}, "goal"),
    ({"name": "오디", "tone": "밝고 에너지 넘치는", "traits": ["긍정적인"]}, "empathy"),
]

# 지난 회기 미션. 절반쯤은 미션 없이 시작한다(0단계 건너뜀).
MISSIONS = [
    "점심 먹고 10분 산책하기",
    "자기 전에 오늘 잘한 일 하나 메모하기",
    "그 생각이 들 때 메모해두고 저녁에 다시 읽어보기",
    "친구에게 안부 메시지 하나 보내기",
    "할 일 목록에서 가장 작은 일 하나만 끝내기",
    "물 한 잔 마시고 3분 동안 천천히 숨쉬기",
]
MISSION_RESULTS = ["해봤다", "못 했다", "절반쯤 했다"]

USER_SIM_PROMPT = """너는 감정 일기 앱에서 상담봇과 대화하는 사용자 역할이다.

[오늘 있었던 일] {diary}
[말하는 방식] {style}
{mission_note}
규칙:
- 한국어 구어체로 1~2문장만 말한다. 존댓말과 반말 중 하나를 골라 끝까지 지킨다.
- 상담봇의 마지막 말에 대답한다. 모르면 모르겠다고 해도 된다.
- 감정이나 생각을 물으면 위 상황에 맞게 구체적으로 답한다.
- 자해·자살·폭력 이야기는 하지 않는다.
- 상담봇의 말을 그대로 따라 하지 않는다.
사용자가 할 말만 출력한다. 따옴표나 설명을 붙이지 않는다."""


def _session_context(rng: random.Random) -> dict:
    scenario = rng.choice(SCENARIOS)
    persona, style = rng.choice(PERSONAS)
    user_style = rng.choice(USER_STYLES)
    has_mission = rng.random() < 0.5
    return {
        "persona": persona,
        "style": style,
        "user_style": user_style,
        "emotions": scenario["emotions"],
        "signals": scenario["signals"],
        "diary_summary": scenario["diary_summary"],
        "recent_themes": scenario["recent_themes"],
        "incongruent": user_style.startswith("괜찮다고"),
        "last_mission": rng.choice(MISSIONS) if has_mission else None,
        "mission_result": rng.choice(MISSION_RESULTS) if has_mission else None,
    }


def system_prompt_for(ctx: dict, stage: int) -> str:
    """그 턴에 서비스가 상담봇에게 주는 시스템 프롬프트 (routes/counsel.py와 같은 순서)."""
    prompt = build_system_prompt(
        persona=ctx["persona"],
        emotions=ctx["emotions"],
        incongruent=ctx["incongruent"],
        signals=ctx["signals"] or None,
        diary_summary=ctx["diary_summary"],
        recent_themes=ctx["recent_themes"] or None,
    )
    return prompt + counsel_cbt.build_cbt_prompt(
        stage, style=ctx["style"], last_mission=ctx["last_mission"]
    )


def history_for(turns: list[dict]) -> list[dict]:
    """서비스처럼 지난 턴은 평문으로 쌓는다(상담봇 JSON이 아니라 reply만)."""
    messages: list[dict] = []
    for t in turns:
        messages.append({"role": "user", "content": t["user"]})
        messages.append({"role": "assistant", "content": t["reply"]})
    return messages


def knows_history(ctx: dict) -> bool:
    """'지난번'이라는 말이 지어낸 기억이 아닌 경우 — 최근 주제나 지난 미션이 있을 때."""
    return bool(ctx["recent_themes"]) or bool(ctx["last_mission"])


def problems(raw: str, stage: int, user_texts: list[str], ctx: dict) -> list[str]:
    """상담봇 응답 하나의 문제 목록. 비어 있으면 학습에 써도 된다."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ["json_parse"]
    if not isinstance(data, dict):
        return ["json_shape"]
    reply = str(data.get("reply") or "").strip()
    if not reply:
        return ["empty_reply"]
    if not isinstance(data.get("advance"), bool):
        return ["advance_type"]
    extracted = data.get("extracted", {})
    if not isinstance(extracted, dict):
        return ["extracted_type"]
    found = [
        v.code
        for v in check_reply(
            reply, user_texts=user_texts, has_recent_themes=knows_history(ctx)
        )
    ]
    unknown = set(extracted) - STAGE_KEYS[stage]
    if unknown:
        found.append("extracted_key:" + ",".join(sorted(unknown)))
    return found


def _violations(raw: str, user_texts: list[str], ctx: dict) -> list:
    try:
        reply = str(json.loads(raw).get("reply") or "")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []
    return check_reply(reply, user_texts=user_texts, has_recent_themes=knows_history(ctx))


def _feedback(raw: str, user_texts: list[str], ctx: dict) -> str:
    """다시 쓸 때 시스템 프롬프트 끝에 붙일 지시. JSON이 깨졌으면 형식만 다시 알려준다."""
    violations = _violations(raw, user_texts, ctx)
    if violations:
        return feedback_for(violations)
    return "\n\n[응답 재작성 지시] 출력 형식의 JSON 객체 하나만, 단계에 맞는 extracted 키로 다시 쓴다."


def _repair_soft(raw: str, stage: int, user_texts: list[str], ctx: dict) -> tuple[str, list[str]]:
    """가벼운 위반만 남은 응답을 repair()로 고친다. 심각한 위반이나 형식 오류면 그대로 둔다."""
    violations = _violations(raw, user_texts, ctx)
    if not violations or any(v.severity == HARD for v in violations):
        return raw, problems(raw, stage, user_texts, ctx)
    data = json.loads(raw)
    data["reply"] = repair(str(data["reply"]))
    fixed = json.dumps(data, ensure_ascii=False)
    return fixed, problems(fixed, stage, user_texts, ctx)


def simulate_user(ctx: dict, turns: list[dict], sim_model: str) -> str:
    note = ""
    if ctx["last_mission"]:
        note = (
            f"[지난 상담에서 정한 미션] {ctx['last_mission']} — 결과: {ctx['mission_result']}. "
            "상담봇이 물으면 그대로 말한다.\n"
        )
    prompt = USER_SIM_PROMPT.format(
        diary=ctx["diary_summary"], style=ctx["user_style"], mission_note=note
    )
    # 시뮬레이터 입장에서는 상담봇 말이 상대(user), 자기 말이 assistant다.
    messages = [{"role": "user", "content": "오늘 하루 어땠는지 편하게 이야기해줄래요?"}]
    for t in turns:
        messages.append({"role": "assistant", "content": t["user"]})
        messages.append({"role": "user", "content": t["reply"]})
    text = llm_client.chat(prompt, messages, temperature=0.9, max_tokens=120, model=sim_model)
    return text.strip().strip('"').strip()


def run_session(ctx: dict, bot_model: str, sim_model: str) -> dict:
    turns: list[dict] = []
    stage, stage_turn = counsel_cbt.FIRST_STAGE, 0
    end_reason = "max_turns"
    rejected: list[str] = []

    for _ in range(MAX_TURNS):
        user_text = simulate_user(ctx, turns, sim_model)
        if not user_text:
            end_reason = "empty_user"
            break
        # 위험 발화는 서비스에서 LLM으로 가지 않으므로 학습 데이터에 넣지 않는다.
        if assess(user_text).level is not RiskLevel.NONE:
            end_reason = "risk"
            break

        stage = counsel_cbt.resolve_stage(stage, ctx["last_mission"])
        system = system_prompt_for(ctx, stage)
        messages = history_for(turns) + [{"role": "user", "content": user_text}]
        user_texts = [t["user"] for t in turns] + [user_text]

        raw, found, feedback = "", ["no_call"], ""
        for _attempt in range(1 + BOT_RETRIES):
            raw = llm_client.chat(
                system + feedback,
                messages,
                json_mode=True,
                max_tokens=BOT_MAX_TOKENS,
                model=bot_model,
            )
            found = problems(raw, stage, user_texts, ctx)
            if not found:
                break
            rejected.extend(found)
            # 서비스(verify)처럼 어긴 규칙을 알려주고 다시 쓰게 한다.
            feedback = _feedback(raw, user_texts, ctx)
        if found:
            # 가벼운 위반(질문 2개·길이 등)만 남았으면 서비스처럼 잘라서 고친다.
            raw, found = _repair_soft(raw, stage, user_texts, ctx)
        if found:
            end_reason = "bot_rule:" + found[0]
            break

        out = counsel_cbt.parse_output(raw)
        turns.append(
            {
                "stage": stage,
                "stage_turn": stage_turn,
                "user": user_text,
                "reply": out.reply,
                "advance": out.advance,
                "extracted": out.extracted,
            }
        )
        stage, stage_turn, done = counsel_cbt.next_state(stage, stage_turn, out.advance)
        if done:
            end_reason = "done"
            break

    return {
        "id": uuid.uuid4().hex[:12],
        "bot_model": bot_model,
        "context": ctx,
        "turns": turns,
        "end_reason": end_reason,
        "rejected": rejected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CBT 단계형 상담 SFT 데이터 생성")
    parser.add_argument("--count", type=int, default=5, help="생성할 회기 수")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default="gpt-6-luna", help="상담봇 역할 모델 (서비스와 같게)")
    parser.add_argument("--sim-model", default="gpt-6-luna", help="사용자 역할 모델")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if not get_settings().llm_api_key:
        raise SystemExit(".env의 LLM_API_KEY가 비어 있습니다.")

    rng = random.Random(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    finished = 0
    with args.out.open("a", encoding="utf-8") as f:
        for i in range(args.count):
            ctx = _session_context(rng)
            try:
                session = run_session(ctx, args.model, args.sim_model)
            except Exception as e:  # 네트워크·요금 한도 등 — 이번 회기만 건너뛴다
                print(f"[{i + 1}/{args.count}] 호출 실패 — {type(e).__name__}: {e}")
                continue
            f.write(json.dumps(session, ensure_ascii=False) + "\n")
            f.flush()
            if session["end_reason"] == "done":
                finished += 1
            stages = sorted({t["stage"] for t in session["turns"]})
            print(
                f"[{i + 1}/{args.count}] {session['id']} | {len(session['turns'])}턴 | "
                f"단계 {stages} | {session['end_reason']}"
            )

    print(f"\n완주 {finished}/{args.count}회기 → {args.out}")
    print("다음: python -X utf8 scripts/prepare_cbt_sft_data.py --review")


if __name__ == "__main__":
    main()