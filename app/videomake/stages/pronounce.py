"""대사 발음 표기(로마자). Veo에 한글 대사와 함께 넘겨 받침을 흘려 읽지 않게 한다.

"오늘 저녁은 쌈 싸 먹자"를 Veo가 두 번 다 "쌀 싸 먹자"로 읽었다(2026-11 할머니 텃밭 컷 6). 받침 ㅁ 뒤에
ㅆ이 오면 받침을 흘렸다. 글자마다 받침까지 적은 로마자를 함께 주면 받침 소리를 지킨다.
연음·동화 같은 발음 규칙은 적용하지 않는다 — 글자 그대로 적어야 빠진 받침이 드러난다.
"""

from __future__ import annotations

_INITIAL = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_MEDIAL = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
           "yu", "eu", "ui", "i"]
_FINAL = ["", "k", "k", "k", "n", "n", "n", "t", "l", "l", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t",
          "ng", "t", "t", "k", "t", "p", "t"]


def romanize(text: str) -> str:
    """한글을 글자(음절)마다 로마자로. 음절 사이는 붙이고, 띄어쓰기·문장부호는 그대로 둔다."""
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            initial, rest = divmod(code, 588)
            medial, final = divmod(rest, 28)
            out.append(_INITIAL[initial] + _MEDIAL[medial] + _FINAL[final])
        else:
            out.append(ch)
    return "".join(out)
