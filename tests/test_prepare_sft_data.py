"""SFT 데이터 정제 — 위반·위기·평가 문장이 든 대화를 걸러내는지."""

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_sft_data.py"
_spec = importlib.util.spec_from_file_location("prepare_sft_data", _PATH)
prep = importlib.util.module_from_spec(_spec)
sys.modules["prepare_sft_data"] = prep
_spec.loader.exec_module(prep)


def _conv(*pairs):
    out = []
    for user, bot in pairs:
        out += [{"role": "user", "content": user}, {"role": "assistant", "content": bot}]
    return out


def test_clean_conversation_passes():
    conv = _conv(("발표 망쳤어", "많이 속상했겠어요. 어떤 장면이 제일 남아요?"),
                 ("질문에 대답을 못 했어", "그 순간 어떤 생각이 들었나요?"))
    assert prep.check_conversation(conv, set()) is None


def test_multi_question_is_dropped():
    conv = _conv(("발표 망쳤어", "속상했겠어요. 왜 그랬어요? 누가 뭐라 했어요?"),
                 ("응", "그렇군요."))
    assert prep.check_conversation(conv, set()) == "violation"


def test_crisis_utterance_is_dropped():
    conv = _conv(("요즘 죽고 싶다는 생각이 자주 들어", "말해 줘서 고마워요."), ("응", "네."))
    assert prep.check_conversation(conv, set()) == "crisis"


def test_eval_sentence_is_dropped():
    conv = _conv(("응 다 물어봐", "어떤 장면이 먼저 떠올라요?"), ("음", "천천히 말해도 돼요."))
    assert prep.check_conversation(conv, {prep._norm("응 다 물어봐")}) == "eval_leak"