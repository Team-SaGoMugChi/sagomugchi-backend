"""4. 승인 게이트 — 이미지 검수용 대조표.

렌더 버튼을 누르기 전에 6컷을 한 화면에서 나란히 보게 만드는 것이 목적이다.
캐릭터가 컷마다 다른 사람으로 보이는지, 카메라가 너무 가까운지는
프롬프트를 읽어서는 알 수 없고 눈으로 봐야 안다.
"""

from __future__ import annotations

import html
from pathlib import Path

from ..job import JobStore
from ..models import Storyboard

_CSS = """
:root{color-scheme:light dark;--bg:#faf9f7;--fg:#1c1b19;--muted:#6b6862;--line:#e2ded7;--ok:#2e7d47}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--fg:#eceae6;--muted:#9a958c;--line:#2f2d29}}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--bg);color:var(--fg);
 font:14px/1.6 -apple-system,BlinkMacSystemFont,"Pretendard","Apple SD Gothic Neo",sans-serif}
h1{font-size:20px;margin:0 0 4px}
.meta{color:var(--muted);margin-bottom:28px}
.sheet{margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid var(--line)}
.sheet img{max-width:min(100%,720px);border-radius:8px;border:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:24px}
.cut{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:transparent}
.cut img{display:block;width:100%;aspect-ratio:9/16;object-fit:cover;background:var(--line)}
.cut .body{padding:12px 14px}
.idx{font-weight:600}
.tag{display:inline-block;font-size:11px;color:var(--muted);border:1px solid var(--line);
 border-radius:99px;padding:1px 8px;margin-left:6px}
.nar{margin:8px 0 10px;font-size:15px}
details{font-size:12px;color:var(--muted)}
details+details{margin-top:4px}
pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 0;font-size:11px;line-height:1.5}
.approved{color:#2e7d47;font-weight:600}
.pending{color:#b26a00;font-weight:600}
"""


def build_review(sb: Storyboard, job: JobStore) -> Path:
    approved = job.approved_cuts()
    parts = [
        "<style>", _CSS, "</style>",
        f"<h1>{html.escape(job.job_id)} — 컷 이미지 검수</h1>",
        (
            f'<div class="meta">주인공 {html.escape(sb.protagonist.name)} · '
            f"{len(sb.cuts)}컷 · 총 {sb.total_seconds}초 · "
            f"승인 {len(approved)}/{len(sb.cuts)}</div>"
        ),
    ]

    if job.character_sheet_path.exists():
        rel = job.character_sheet_path.relative_to(job.dir)
        parts += [
            '<div class="sheet"><div class="idx">캐릭터 시트</div>',
            f'<img src="{rel}" alt="character sheet"></div>',
        ]

    parts.append('<div class="grid">')
    for cut in sb.cuts:
        img = job.cut_image(cut.index)
        src = img.relative_to(job.dir) if img.exists() else ""
        state = (
            '<span class="approved">승인됨</span>'
            if cut.index in approved
            else '<span class="pending">미승인</span>'
        )
        parts += [
            '<div class="cut">',
            f'<img src="{src}" alt="cut {cut.index}">' if src else "<div></div>",
            '<div class="body">',
            (
                f'<span class="idx">CUT {cut.index}</span>'
                f'<span class="tag">{cut.camera_distance}</span>'
                f'<span class="tag">{cut.duration_seconds}s</span> {state}'
            ),
            (
                "".join(
                    f'<div class="nar">{html.escape(line.speaker)}: '
                    f"“{html.escape(line.text)}”</div>"
                    for line in cut.dialogue
                )
                if cut.is_dialogue
                else f'<div class="nar">{html.escape(cut.narration or "")}</div>'
            ),
            f"<details><summary>image_prompt</summary><pre>{html.escape(cut.image_prompt)}</pre></details>",
            f"<details><summary>motion_prompt</summary><pre>{html.escape(cut.motion_prompt)}</pre></details>",
            "</div></div>",
        ]
    parts.append("</div>")

    if sb.distortions:
        parts.append("<h1 style='margin-top:36px;font-size:16px'>인지왜곡 분리</h1><div class='grid'>")
        for d in sb.distortions:
            parts.append(
                '<div class="cut"><div class="body">'
                f'<span class="tag">{html.escape(d.kind)}</span>'
                f"<div class='nar'>사실: {html.escape(d.fact)}</div>"
                f"<div class='nar' style='color:var(--muted)'>느껴진 것: {html.escape(d.felt_as)}</div>"
                "</div></div>"
            )
        parts.append("</div>")

    job.review_path.write_text("\n".join(parts), encoding="utf-8")
    return job.review_path
