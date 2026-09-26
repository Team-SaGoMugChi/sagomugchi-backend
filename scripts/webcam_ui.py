"""웹캠 테스트 스크립트 공용: 카메라 열기, 한글 결과 패널 그리기 (Windows/macOS/Linux).

scripts/webcam_face_emotion.py, scripts/diary_emotion_test.py가 같이 쓴다. 화면에만 그리고
프레임은 저장하지 않는다.
"""

import platform
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

# requirements.txt는 서버용이라 화면 창이 없는 opencv-python-headless를 쓴다. mediapipe가 창이 있는
# opencv-contrib-python을 함께 설치하는 경우가 많지만, 설치 순서에 따라 창을 못 여는 환경이 있다.
_HEADLESS_HELP = (
    "OpenCV가 화면 창을 열지 못했어요 (창이 없는 headless 버전이 쓰이는 중).\n"
    "  pip uninstall -y opencv-python-headless opencv-contrib-python\n"
    "  pip install opencv-contrib-python\n"
    "로 창이 있는 버전을 다시 설치한 뒤 실행해 주세요."
)

DISPLAY_SIZE = (1040, 780)
PANEL_WIDTH = 560


def korean_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("한글 폰트를 찾지 못했어요. scripts/webcam_ui.py의 _FONT_CANDIDATES에 폰트 경로를 추가해 주세요.")


def open_camera(index: int = 0) -> cv2.VideoCapture:
    # Windows 기본 백엔드(MSMF)는 여는 데 수 초가 걸려서 DirectShow를 쓴다.
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if platform.system() == "Windows" else cv2.VideoCapture(index)
    if not cap.isOpened():
        raise SystemExit(
            "웹캠을 열 수 없어요. 다른 프로그램(Zoom 등)이 카메라를 쓰고 있는지, "
            "macOS라면 시스템 설정 > 개인정보 보호 > 카메라에서 터미널 권한을 확인해 주세요."
        )
    return cap


def show(window: str, frame: np.ndarray) -> int:
    """창에 그리고 눌린 키를 돌려준다."""
    try:
        cv2.imshow(window, frame)
    except cv2.error as exc:
        raise SystemExit(_HEADLESS_HELP) from exc
    return cv2.waitKey(1) & 0xFF


class Panel:
    """왼쪽 반투명 패널에 한글 줄을 그린다.

    줄 형식: (종류, 값) — 종류는 title·big·text·dim·warn(값=문자열), bar(값=(이름, 0~1)),
    valence(값=−1~1).
    """

    _COLORS = {
        "title": (255, 230, 120, 255),
        "big": (120, 220, 255, 255),
        "text": (255, 255, 255, 255),
        "dim": (170, 170, 170, 255),
        "warn": (255, 120, 120, 255),
    }

    def __init__(self) -> None:
        self.font = korean_font(18)
        self.font_big = korean_font(22)

    def render(self, frame: np.ndarray, lines: list[tuple[str, object]]) -> np.ndarray:
        frame = cv2.resize(frame, DISPLAY_SIZE)
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([0, 0, PANEL_WIDTH, img.size[1]], fill=(0, 0, 0, 165))
        y = 10
        for kind, value in lines:
            if kind == "bar":
                label, level = value
                draw.text((12, y), label, font=self.font, fill=self._COLORS["text"])
                draw.rectangle([80, y + 6, 330, y + 18], outline=(120, 120, 120, 255))
                draw.rectangle([80, y + 6, 80 + int(250 * max(0.0, min(level, 1.0))), y + 18], fill=(90, 170, 255, 255))
                draw.text((340, y), f"{level:.2f}", font=self.font, fill=self._COLORS["dim"])
                y += 26
            elif kind == "valence":
                mid, half = 205, 125
                draw.text((12, y), "긍정도", font=self.font, fill=self._COLORS["text"])
                draw.rectangle([mid - half, y + 6, mid + half, y + 18], outline=(120, 120, 120, 255))
                end = mid + int(half * max(-1.0, min(value, 1.0)))
                color = (90, 220, 120, 255) if value >= 0 else (255, 110, 110, 255)
                draw.rectangle([min(mid, end), y + 6, max(mid, end), y + 18], fill=color)
                draw.line([mid, y + 3, mid, y + 21], fill=(255, 255, 255, 255))
                draw.text((340, y), f"{value:+.2f}", font=self.font, fill=self._COLORS["dim"])
                y += 32
            else:
                big = kind in ("title", "big")
                draw.text((12, y), str(value), font=self.font_big if big else self.font, fill=self._COLORS[kind])
                y += 34 if kind == "title" else 32 if big else 25
        img = Image.alpha_composite(img, overlay).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def wrap(text: str, width: int = 28) -> list[str]:
    return [text[i:i + width] for i in range(0, len(text), width)] or [""]
