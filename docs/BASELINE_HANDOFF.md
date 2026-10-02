# Baseline feature contract v2

Firestore: `users/{uid}/meta/baseline`. New measurements store `featureVersion: 2`; the API returns `feature_version: 2`. Documents without a version are version 0, and the previous six-voice/four-face contract is version 1. Versions 0 and 1 remain readable but must be measured again before Step2 because they lack the statistics required by multimodal fusion.

| voice key | Meaning / unit |
|---|---|
| pitchMean | Mean measured F0, Hz; retained for existing consumers. NOT median or semitones. |
| f0Std | Population standard deviation of measured F0, Hz (numpy std, ddof=0). |
| speechRate | Estimated syllable nuclei per second, not STT word count. |
| voicedRatio | Fraction of frames pYIN marks voiced, 0–1. |
| durationSec | Full recording duration in seconds, including silence. |
| energyMean | Mean RMS amplitude; sensitive to microphone/gain/distance, not calibrated across sessions. |
| windowPitchMean / windowPitchStd | Mean and population standard deviation of F0 among voiced three-second windows. |
| windowEnergyMean / windowEnergyStd | Mean and population standard deviation of RMS among voiced windows. |
| windowSpeechRate / windowSpeechRateStd | Mean and population standard deviation of estimated syllables/second among voiced windows. |
| windowCount / windowUsedCount | All windows and voiced windows used for the statistics. |

`measuredAt` is UTC ISO-8601. The face map keeps the existing four ratios and adds log-space mean/std fields for AU1, AU2, AU4, AU5, AU6, AU7, AU12, AU15, and AU17 (`au*LogMean`, `au*LogStd`), plus `auFrameCount` and `auTotalFrames`. The app captures multiple still frames during the measurement. Legacy clients may continue to send one `face_image`; new clients send repeated `face_images` multipart parts. AU statistics use every submitted frame with a detected face. The modality service applies its documented standard-deviation floor when variance is low.

The full-recording fields remain for compatibility and quality checks. The window and AU statistics are the actual v2 z-score inputs. Silence windows are excluded so pauses do not look like emotion change. Recording length remains metadata rather than emotion intensity.

For the denser baseline capture, the client attempts one photo per second (up to 400) and sends `face_timeline` as semicolon-separated `recordingMilliseconds,promptFlag` entries aligned with the repeated `face_images` parts. `promptFlag=1` marks app TTS, not user speech. The new client pauses recording and the recording-relative clock during spoken prompts and skips prompt photos; if pausing fails, it shows the text without playing TTS. The server matches other frames to the existing pYIN voiced timeline in a 0.5-second neighborhood (three-second voice windows are a fallback) and stores `speakingFrameCount`, `silentFrameCount`, and AU mean/std per group (`speakingAu*`, `silentAu*`). Diary Step1 attempts one photo per second during user turns and sends repeated `face_images` with `face_timeline`; turn timestamps are shifted by preceding WAV PCM durations because Step1 concatenates the turns. Step2 classifies each frame with the same pYIN neighborhood and compares its AU against the matching speaking/silent baseline. Missing timeline or group values retain the full-session AU reference for older v2 clients. Actual capture rate, recorder pause/resume, and voiced/silent boundaries still require device validation. Older clients that record over TTS can still produce contaminated voice baselines; frame prompt flags alone do not remove those audio samples.

```json
{"voice":{"pitchMean":219.9,"f0Std":28.4,"speechRate":4.2,"voicedRatio":0.61,"durationSec":352.0,"energyMean":0.031,"windowPitchMean":218.0,"windowPitchStd":12.0,"windowEnergyMean":0.032,"windowEnergyStd":0.004,"windowSpeechRate":4.1,"windowSpeechRateStd":0.5,"windowCount":117,"windowUsedCount":94},"face":{"eyeAspectRatio":0.28,"mouthAspectRatio":0.11,"mouthWidthRatio":1.42,"eyebrowRaiseRatio":0.38,"au1LogMean":-2.0,"au1LogStd":0.0,"auFrameCount":1,"auTotalFrames":1},"measuredAt":"2026-09-22T00:00:00+00:00","featureVersion":2}
```

Example values illustrate the schema, not a real user's measurement. Text has no baseline handoff field. Invalid/missing F0 standard deviation or out-of-range voiced ratio is rejected before overwriting a saved baseline.

`POST /diary/step2/analyze` requires the same v2 contract in multipart fields:

- `baseline_voice`: JSON object containing the full-recording and window fields above.
- `baseline_face`: JSON object containing the four ratios and all AU mean/std/count fields.
- `baseline_feature_version`: `2`.
- `baseline_measured_at`: UTC ISO-8601 timestamp.

Missing, legacy, non-finite, or out-of-range values return HTTP 422 with
`detail.code = "baseline_remeasurement_required"`. The client should send the user back to baseline remeasurement instead of silently calculating with fewer deltas.

The daily `voice_file` and `face_image` are validated before delta calculation.
Unreadable audio, no measurable voiced signal, unreadable images, and captures
without a detected face return HTTP 422 with `invalid_audio`,
`voice_not_detected`, `invalid_face_image`, or `face_not_detected`. Each response
includes a Korean `detail.message` that the client can show as a retry prompt.

New diary clients may send repeated `face_images` and `face_timeline` in the same `recordingMilliseconds,0` format. Step2 rejects malformed or out-of-order timestamps with `invalid_face_timeline`; legacy single-image requests still use the overall face reference. All 300 backend tests pass, including the speaking/silent group comparison. Device timing and upload latency remain unverified. PR #57 is published, not merged into `develop`.

The Step2 response model also rejects non-finite values and enforces 0–100 for
emotion scores/intensity and 0–1 for text-emotion probabilities. This prevents
invalid calculations from crossing the API boundary into Firestore or counsel
context.

The Step2 response now also contains `signals`, `incongruent`,
`incongruence_sources`, and `modalities`. These are the server-calculated values
forwarded to counseling; the client does not reinterpret thresholds. Failure to
load the AU model returns HTTP 503 `emotion_analysis_unavailable` rather than
silently using a different formula.
# 2026-09-27 Windows 실기기 검증

- MediaPipe 0.10.14가 Windows 절대 경로 앞에 패키지 경로를 덧붙여 FaceLandmarker 모델을 열지 못하는 문제를 확인했다. 검증된 모델 파일을 `model_asset_buffer`로 전달하도록 수정해 운영체제 경로 해석을 제거했다.
- 보존된 실측 음성·얼굴 파일로 재시도해 음성 구간 분석, 얼굴 AU 분석, Firestore 저장을 거쳐 `POST /baseline` 200 응답을 확인했다. 앱 완료 화면에서도 실제 측정 시각과 얼굴·음성 저장 완료를 확인했다. 개인 측정 원값과 사용자 ID는 문서에 기록하지 않는다.
