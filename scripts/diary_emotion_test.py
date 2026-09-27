"""대화 일기 감정 분석 테스트: python -m scripts.diary_emotion_test

앱 Step1처럼 "오늘 있었던 일" 한 가지를 자유롭게 말하면 STT(CLOVA) → 텍스트(KOTE) + 표정 +
목소리 → 멀티모달 융합으로 분석하고, 결과를 JSON 두 개로 남긴다.
    .cache/diary_tests/<시각>_analysis.json  분석 원본 (문장별 결과, 녹음 후 고른 실제 감정 포함)
    .cache/diary_tests/<시각>_video.json     숏폼 영상용 (oddo.diary_emotion.v0-sample: 장면 후보·전환점)
말한 내용이 들어가므로 .cache 아래(Git 제외)에 저장한다. 녹음·영상 프레임은 저장하지 않는다.

필요: .env의 CLOVA_SPEECH_INVOKE_URL·CLOVA_SPEECH_SECRET, pip install -r requirements-kote.txt,
웹캠·마이크. 녹음 한 번마다 CLOVA를 한 번 호출한다(과금).

키: b 평소 측정(20초, 질문에 평소처럼 답하기) / r 말하기 시작·끝 / 1~7 실제 느낀 감정 고르기 /
    s 실제 감정 저장 / q 종료
"""

import io
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx
import numpy as np
import soundfile as sf

from app.core.config import get_settings
from app.services.face_au import FaceAu, get_face_au_extractor
from app.services.kote_emotion import MAPPING_VERSION, MODEL_ID, TextEmotionUnavailable
from app.services.modality_emotion import (
    VoiceArousal,
    face_emotion_from_frames,
    face_log_summary,
    voice_arousal_from_summary,
    voice_timeline,
)
from app.services.multimodal_fusion import fuse_multimodal, text_valence
from app.services.stt import _RECOGNIZE_PARAMS
from app.services.text_emotion import EMOTION_LABELS, get_text_emotion_classifier
from app.services.voice_windows import WINDOW_SEC, analyze_windows, summarize_windows
from scripts.webcam_ui import Panel, open_camera, show, wrap

WINDOW = "Oddo diary emotion test"
SR = 16000
BASELINE_SEC = 20.0
OUT_DIR = Path(".cache/diary_tests")
BASELINE_PROMPT = ["아래 질문에 평소처럼 편하게 답해 주세요", "· 오늘 아침에 뭐 했어요?",
                   "· 요즘 학교에서 주로 뭐 해요?", "· 주말에는 보통 뭐 하면서 쉬어요?"]
DIARY_PROMPT = "오늘 있었던 일을 통화하듯 편하게 이야기해 주세요"  # 앱 Step1과 같은 안내
DIARY_TIPS = ["한 가지 일을 1~3분 쭉 이야기해 주세요", "카메라 쪽을 보며 말하면 표정이 잘 잡혀요"]
SELF_LABELS = {ord(str(i + 1)): label for i, label in enumerate([*EMOTION_LABELS, "중립"])}

VIDEO_GUIDE = {
    "목적": "대화형 일기 1편의 원문과 감정 분석 결과. 숏폼 영상의 장면 구성·분위기 결정에 쓰는 입력.",
    "diary.transcript": "사용자가 말한 내용을 STT(CLOVA)로 받아 적은 원문. 다듬지 않았다.",
    "시간(start_sec/end_sec)": "녹음 시작부터 잰 초. 문장 시간은 STT의 단어별 시간으로 계산했다.",
    "emotion_scores": "감정 6종(기쁨·슬픔·분노·불안·상처·당황) 비율, 합 100. 0인 감정은 생략.",
    "tone": "긍정 / 중립 / 부정. 영상 분위기(밝음·잔잔함·가라앉음)에 대응.",
    "intensity": "감정 강도 0~100. 높을수록 감정이 뚜렷하다.",
    "emotion_overall.arc": "일기 전체의 감정 흐름을 한 줄로 요약한 것.",
    "emotion_overall.signals": "평소보다 뚜렷하게 달라진 표정·목소리를 문장으로. 표정 연출 힌트.",
    "scenes": "톤이 같은 연속 문장을 묶은 장면 후보. 감정이 바뀌는 곳에서 나뉜다. 길면 영상 생성 단위(약 8초)로 더 쪼개면 된다.",
    "turning_points": "감정 톤이 바뀌는 시점. 영상에서 분위기·음악·표정이 바뀌어야 하는 곳.",
    "incongruent": "말한 감정과 표정·목소리가 어긋난 경우 true, incongruence_sources는 어긋난 쪽(face/voice).",
    "한계": "감정 분석 가중치는 이론 기반 잠정값이다. 표정·목소리 변화가 작으면 감정은 주로 말한 내용(텍스트)에서 나온다.",
}


# ---- 분석 결과 계산 (카메라·마이크 없이 테스트할 수 있는 부분) -------------------------------------

def split_sentences(segment: dict) -> list[tuple[float, float, str]]:
    """CLOVA segment → (시작 초, 끝 초, 문장). words에는 시간은 있지만 문장부호가 없어서, 문장부호로
    나눈 문장을 단어 개수로 words에 맞춘다. 개수가 안 맞으면 segment 하나를 그대로 쓴다."""
    text = (segment.get("text") or "").strip()
    words = segment.get("words") or []
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", text) if p.strip()]
    counts = [len(p.split()) for p in parts]
    if len(parts) <= 1 or sum(counts) != len(words):
        return [(segment["start"] / 1000, segment["end"] / 1000, text)]
    sentences, i = [], 0
    for part, n in zip(parts, counts):
        sentences.append((words[i][0] / 1000, words[i + n - 1][1] / 1000, part))
        i += n
    return sentences


def tone_of(scores_0_100: dict[str, float]) -> str:
    value = text_valence({k: v / 100 for k, v in scores_0_100.items()})
    return "긍정" if value > 0.2 else "부정" if value < -0.2 else "중립"


def _duration(sentence: dict) -> float:
    return sentence["end_sec"] - sentence["start_sec"]


def weighted_scores(sentences: list[dict]) -> dict[str, float]:
    """문장별 점수를 문장 길이로 가중 평균 — 일기 전체를 한 번에 분류하면 가장 강한 감정 하나만 남는다."""
    counted = [s for s in sentences if s["emotion"]]
    total = sum(_duration(s) for s in counted) or 1
    return {k: round(sum(s["emotion_scores"].get(k, 0.0) * _duration(s) for s in counted) / total, 1)
            for k in EMOTION_LABELS}


def top_labels(scores: dict[str, float], n: int = 2) -> list[str]:
    return [k for k, v in sorted(scores.items(), key=lambda kv: -kv[1]) if v >= 10][:n]


def _avg_intensity(sentences: list[dict]) -> int:
    return round(sum(s["intensity"] * _duration(s) for s in sentences) / sum(_duration(s) for s in sentences))


def group_scenes(sentences: list[dict]) -> list[list[dict]]:
    """톤이 같은 연속 문장을 묶는다. 중립 문장은 앞뒤 톤이 같으면 앞 장면에 붙이고(감정 없는 문장
    조각이 장면을 쪼개지 않게), 다르면 다음 장면의 전환 문장으로 붙인다."""
    groups: list[dict] = []
    for i, s in enumerate(sentences):
        if s["tone"] == "중립" and groups:
            nxt = next((x["tone"] for x in sentences[i + 1:] if x["tone"] != "중립"), None)
            if nxt is None or nxt == groups[-1]["tone"]:
                groups[-1]["items"].append(s)
            else:
                groups.append({"tone": nxt, "items": [s]})
            continue
        if groups and groups[-1]["tone"] in (s["tone"], "중립"):
            groups[-1]["tone"] = s["tone"]
            groups[-1]["items"].append(s)
        else:
            groups.append({"tone": s["tone"], "items": [s]})
    return [g["items"] for g in groups]


def to_video_json(analysis: dict) -> dict:
    """분석 원본 → 숏폼 영상용 형식(oddo.diary_emotion.v0-sample)."""
    sentences = [{
        "index": t["index"], "start_sec": t["start_sec"], "end_sec": t["end_sec"], "text": t["text"],
        "emotion": t["emotion"], "tone": t["tone"], "intensity": t["intensity"],
        "emotion_scores": {k: v for k, v in t["emotion_scores"].items() if v > 0},
    } for t in analysis["timeline"]]
    scenes = []
    for order, items in enumerate(group_scenes(sentences), start=1):
        scores = weighted_scores(items)
        scenes.append({
            "order": order, "start_sec": items[0]["start_sec"], "end_sec": items[-1]["end_sec"],
            "tone": tone_of(scores), "emotions": top_labels(scores), "intensity": _avg_intensity(items),
            "sentence_indexes": [s["index"] for s in items], "text": " ".join(s["text"] for s in items),
        })
    turning = [{"at_sec": b["start_sec"], "from": a["tone"], "to": b["tone"], "sentence": b["text"].split(". ")[0]}
               for a, b in zip(scenes, scenes[1:]) if a["tone"] != b["tone"]]
    overall = weighted_scores(sentences) if sentences else dict.fromkeys(EMOTION_LABELS, 0.0)
    source = analysis["emotion_overall"]
    return {
        "설명": VIDEO_GUIDE,
        "schema": "oddo.diary_emotion.v0-sample",
        "diary": {"duration_sec": analysis["diary"]["duration_sec"], "transcript": analysis["diary"]["transcript"]},
        "emotion_overall": {
            "keywords": top_labels(overall),
            "scores": {k: v for k, v in sorted(overall.items(), key=lambda kv: -kv[1]) if v > 0},
            "tone": tone_of(overall),
            "intensity": _avg_intensity(sentences) if sentences else 0,
            "arc": " → ".join(f'{s["tone"]}({", ".join(s["emotions"])})' for s in scenes),
            "signals": source["signals"],
            "incongruent": source["incongruent"],
            "incongruence_sources": source["incongruence_sources"],
        },
        "scenes": scenes,
        "turning_points": turning,
        "sentences": sentences,
    }


# ---- 녹음·분석 ----------------------------------------------------------------------------------

class Recorder:
    """마이크를 계속 열어 두고, 켜져 있을 때만 모은다."""

    def __init__(self) -> None:
        self.active = False
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()

    def callback(self, indata, _frames, _time, _status) -> None:
        if self.active:
            with self._lock:
                self._chunks.append(indata[:, 0].copy())

    def take_wav(self) -> bytes:
        with self._lock:
            y = np.concatenate(self._chunks) if self._chunks else np.zeros(1, dtype=np.float32)
            self._chunks.clear()
        buffer = io.BytesIO()
        sf.write(buffer, y, SR, format="WAV")
        return buffer.getvalue()


def clova_with_segments(audio: bytes) -> dict:
    """app/services/stt.py와 같은 요청이지만 CLOVA의 문장 구간(segments)을 그대로 받는다."""
    settings = get_settings()
    response = httpx.post(
        (settings.clova_speech_invoke_url or "").rstrip("/") + "/recognizer/upload",
        headers={"X-CLOVASPEECH-API-KEY": settings.clova_speech_secret or ""},
        files={"media": ("diary.wav", audio, "audio/wav"),
               "params": (None, json.dumps(_RECOGNIZE_PARAMS), "application/json")},
        timeout=max(settings.clova_speech_timeout_sec, 180.0),  # 몇 분짜리 일기는 오래 걸린다
    )
    response.raise_for_status()
    return response.json()


def analyze(audio: bytes, frames: list[tuple[float, FaceAu]], face_base, voice_base, classifier) -> dict:
    payload = clova_with_segments(audio)
    transcript = (payload.get("text") or "").strip()
    if not transcript:
        raise ValueError("말소리를 알아듣지 못했어요. 마이크를 확인하고 다시 말해 주세요.")
    windows = analyze_windows(audio)
    moments = voice_timeline(windows, voice_base)

    text = classifier.classify(transcript)
    face = face_emotion_from_frames([f for _, f in frames], face_base)
    voice = voice_arousal_from_summary(summarize_windows(windows), voice_base)
    overall = fuse_multimodal(text, face, voice)

    sentences = [s for seg in payload.get("segments") or [] if (seg.get("text") or "").strip()
                 for s in split_sentences(seg)]
    timeline = []
    for index, (start, end, sentence) in enumerate(sentences):
        seg_face = face_emotion_from_frames([f for t, f in frames if start <= t <= end], face_base)
        arousals = [m.arousal.arousal for m in moments
                    if m.arousal is not None and m.start_sec < end and m.start_sec + WINDOW_SEC > start]
        seg_voice = VoiceArousal(float(np.mean(arousals)), {}) if arousals else None
        fused = fuse_multimodal(classifier.classify(sentence), seg_face, seg_voice)
        best = max(fused.emotion_scores, key=fused.emotion_scores.get)
        timeline.append({
            "index": index, "start_sec": round(start, 2), "end_sec": round(end, 2), "text": sentence,
            "emotion": best if fused.emotion_scores[best] > 0 else None,
            "tone": tone_of(fused.emotion_scores) if fused.emotion_keywords else "중립",
            "emotion_scores": fused.emotion_scores,
            "intensity": fused.emotion_intensity,
            "face_valence": None if seg_face is None else round(seg_face.valence, 2),
            "voice_arousal": None if seg_voice is None else round(seg_voice.arousal, 2),
            "incongruent": fused.incongruent,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "diary": {"transcript": transcript, "duration_sec": round(len(sf.read(io.BytesIO(audio))[0]) / SR, 1)},
        "emotion_overall": {
            "keywords": overall.emotion_keywords,
            "scores": overall.emotion_scores,
            "intensity": overall.emotion_intensity,
            "text_scores": {k: round(v * 100, 1) for k, v in text.scores.items()},
            "face": None if face is None else {"scores": {k: round(v, 2) for k, v in face.scores.items()},
                                               "valence": round(face.valence, 2)},
            "voice_arousal": None if voice is None else round(voice.arousal, 2),
            "incongruent": overall.incongruent,
            "incongruence_sources": overall.incongruence_sources,
            "signals": overall.signals,
        },
        "timeline": timeline,
        "meta": {
            "stt": "Naver CLOVA Speech", "text_emotion": f"{MODEL_ID} / {MAPPING_VERSION}",
            "baseline": {"face_frames": face_base.frame_count, "voice_windows": voice_base.used_count},
        },
    }


def _preflight():
    settings = get_settings()
    if not (settings.clova_speech_invoke_url and settings.clova_speech_secret):
        raise SystemExit(".env에 CLOVA_SPEECH_INVOKE_URL·CLOVA_SPEECH_SECRET이 없어요. 음성 인식 없이는 일기 테스트를 할 수 없어요.")
    try:
        import sounddevice
    except ImportError as exc:
        raise SystemExit("마이크 녹음용 sounddevice가 없어요: pip install sounddevice") from exc
    print("모델 준비 중 (KOTE 첫 로딩은 15초 정도 걸려요)...")
    classifier = get_text_emotion_classifier()
    try:
        classifier.classify("준비")
    except TextEmotionUnavailable as exc:
        raise SystemExit("KOTE 감정 모델을 불러오지 못했어요: pip install -r requirements-kote.txt (docs/KOTE.md)") from exc
    return sounddevice, classifier


def main() -> None:
    sounddevice, classifier = _preflight()
    extractor = get_face_au_extractor()
    panel = Panel()
    recorder = Recorder()
    cap = open_camera()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    state, started = "idle", 0.0
    frames: list[tuple[float, FaceAu]] = []
    face_base = voice_base = None
    result_lines: list[tuple[str, object]] = []
    chosen: set[str] = set()
    analysis_path: Path | None = None
    saved_self = False

    try:
        with sounddevice.InputStream(samplerate=SR, channels=1, dtype="float32", callback=recorder.callback):
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                if state in ("baseline", "recording"):
                    ok, jpg = cv2.imencode(".jpg", frame)
                    frames.append((time.time() - started, extractor.extract(jpg.tobytes())))

                if state == "idle":
                    lines = [("title", "대화 일기 감정 테스트"), ("text", "b: 평소 목소리·얼굴 측정 (20초)")]
                elif state == "baseline":
                    left = BASELINE_SEC - (time.time() - started)
                    lines = [("title", f"평소 측정 중 {max(left, 0):.0f}초")] + [("text", s) for s in BASELINE_PROMPT]
                    if left <= 0:
                        recorder.active = False
                        face_base = face_log_summary([f for _, f in frames])
                        voice_base = summarize_windows(analyze_windows(recorder.take_wav()))
                        frames = []
                        state = "ready" if face_base.frame_count and voice_base.used_count >= 2 else "idle"
                        if state == "idle":
                            print("평소 측정 실패: 얼굴이나 말한 구간이 부족해요. b로 다시 측정해 주세요.")
                elif state == "ready":
                    lines = [("title", "준비 완료"),
                             ("dim", f"평소 얼굴 {face_base.frame_count}프레임, 목소리 {voice_base.used_count}구간")]
                    lines += [("big", part) for part in wrap(DIARY_PROMPT, 20)] + [("dim", s) for s in DIARY_TIPS]
                    lines += [("warn", "r: 말하기 시작"), ("dim", "b: 평소 다시 측정   q: 종료")]
                elif state == "recording":
                    lines = [("title", f"녹음 중 {time.time() - started:.0f}초")]
                    lines += [("big", part) for part in wrap(DIARY_PROMPT, 20)] + [("warn", "r: 끝내고 분석")]
                else:
                    picked = ", ".join(label for label in SELF_LABELS.values() if label in chosen) or "(아직 없음)"
                    lines = result_lines + [
                        ("big", "실제로 느낀 감정은? (여러 개 가능)"),
                        ("text", "1 기쁨 2 슬픔 3 분노 4 불안 5 상처 6 당황 7 중립"),
                        ("text", f"고른 감정: {picked}"),
                        ("dim" if saved_self else "warn", "저장됨 ✓" if saved_self else "s: 내 감정 저장"),
                        ("dim", "r: 다시 말하기   b: 평소 다시 측정   q: 종료"),
                    ]

                key = show(WINDOW, panel.render(frame, lines))
                if key == ord("q"):
                    break
                if key in SELF_LABELS and state == "result" and analysis_path:
                    chosen ^= {SELF_LABELS[key]}
                    saved_self = False
                elif key == ord("s") and state == "result" and analysis_path and chosen:
                    data = json.loads(analysis_path.read_text(encoding="utf-8"))
                    data["self_report"] = {"emotions": [lb for lb in SELF_LABELS.values() if lb in chosen],
                                           "note": "녹음 직후 사용자가 고른 실제 감정 (AI 결과와 비교용)"}
                    analysis_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    saved_self = True
                elif key == ord("b") and state != "recording":
                    recorder.take_wav()
                    recorder.active, frames, started, state = True, [], time.time(), "baseline"
                elif key == ord("r") and state in ("ready", "result"):
                    recorder.take_wav()
                    recorder.active, frames, started, state = True, [], time.time(), "recording"
                elif key == ord("r") and state == "recording":
                    recorder.active, state = False, "result"
                    diary_frames, frames = frames, []
                    chosen, saved_self, analysis_path = set(), False, None
                    show(WINDOW, panel.render(frame, [("title", "분석 중... (30초 정도)")]))
                    try:
                        analysis = analyze(recorder.take_wav(), diary_frames, face_base, voice_base, classifier)
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        analysis_path = OUT_DIR / f"{stamp}_analysis.json"
                        video_path = OUT_DIR / f"{stamp}_video.json"
                        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
                        video = to_video_json(analysis)
                        video_path.write_text(json.dumps(video, ensure_ascii=False, indent=2), encoding="utf-8")
                        print(f"saved -> {analysis_path}\n         {video_path}")
                        overall = video["emotion_overall"]
                        result_lines = [("title", "분석 완료"), ("dim", f"{stamp}_*.json"),
                                        ("big", f"전체: {', '.join(overall['keywords']) or '판단 불가'}")]
                        result_lines += [("text", part) for part in wrap("흐름: " + (overall["arc"] or "-"))[:3]]
                        if overall["incongruent"]:
                            result_lines.append(("warn", "불일치: " + ", ".join(overall["incongruence_sources"])))
                    except Exception as exc:  # 창을 닫지 않고 실패 이유를 보여준다
                        result_lines = [("title", "실패"), ("warn", type(exc).__name__)]
                        result_lines += [("text", part) for part in wrap(str(exc))[:6]]
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
