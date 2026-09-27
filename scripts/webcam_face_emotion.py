"""웹캠 표정 감정 테스트: python -m scripts.webcam_face_emotion

처음 5초 무표정으로 평소 얼굴(baseline)을 잡고, 이후 실시간으로 표정 감정 6종·표정 긍정도·
상담봇에 넘길 변화 문장(signals)을 보여준다. 필요한 건 requirements.txt와 웹캠뿐이다
(표정 모델은 첫 실행 때 .cache/mediapipe로 받는다). 프레임은 저장하지 않는다.

키: b 평소 얼굴 다시 측정 / a AU z-score 보기 / q 종료
"""

import time

import cv2

from app.services.face_au import get_face_au_extractor
from app.services.modality_emotion import describe_signals, face_emotion, face_log_summary, face_z, log_au
from scripts.webcam_ui import Panel, open_camera, show

WINDOW = "Oddo face emotion test"
BASELINE_SEC = 5.0
SMOOTH = 0.3  # 막대가 프레임마다 깜빡이지 않게 지수 평활
ORDER = ("기쁨", "슬픔", "상처", "분노", "불안", "당황")
HEADLINE_MIN = 0.15


def main() -> None:
    extractor = get_face_au_extractor()
    panel = Panel()
    cap = open_camera()
    baseline_frames, baseline, started = [], None, time.time()
    smoothed: dict[str, float] = {}
    show_au = False
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            ok, jpg = cv2.imencode(".jpg", frame)
            result = extractor.extract(jpg.tobytes())

            if baseline is None:
                left = BASELINE_SEC - (time.time() - started)
                baseline_frames.append(result)
                lines = [("title", "평소 얼굴 측정 중"), ("text", f"무표정을 유지해 주세요  {max(left, 0):.1f}초")]
                if left <= 0:
                    summary = face_log_summary(baseline_frames)
                    if summary.frame_count:
                        baseline, smoothed = summary, {}
                    else:
                        baseline_frames, started = [], time.time()
            elif not result.detected:
                lines = [("title", "얼굴을 찾지 못했어요"), ("dim", "카메라 정면에서 조금 더 가까이 앉아 주세요")]
            else:
                z = face_z(log_au(result.au), baseline)
                emotion = face_emotion(z)
                for key, value in {**emotion.scores, "_valence": emotion.valence}.items():
                    smoothed[key] = value if key not in smoothed else smoothed[key] * (1 - SMOOTH) + value * SMOOTH
                top = max(ORDER, key=lambda label: smoothed[label])
                lines = [("title", f"표정 감정: {top}" if smoothed[top] >= HEADLINE_MIN else "표정 감정: 뚜렷하지 않음")]
                lines += [("bar", (label, smoothed[label])) for label in ORDER]
                lines += [("valence", smoothed["_valence"]), ("text", "상담봇에 넘길 문장:")]
                lines += [("text", f"· {s}") for s in describe_signals(emotion.z, None) or ["(뚜렷한 변화 없음)"]]
                if show_au:
                    lines += [("dim", "  ".join(f"{k} {v:+.1f}" for k, v in list(z.items())[i:i + 3])) for i in range(0, len(z), 3)]
                lines.append(("dim", f"평소 얼굴 {baseline.frame_count}프레임"))

            lines.append(("dim", "b: 평소 얼굴 다시 측정   a: AU 보기   q: 종료"))
            key = show(WINDOW, panel.render(frame, lines))
            if key == ord("q"):
                break
            if key == ord("a"):
                show_au = not show_au
            if key == ord("b"):
                baseline_frames, baseline, started = [], None, time.time()
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
