# Baseline feature contract v1

Firestore: `users/{uid}/meta/baseline`. New measurements store `featureVersion: 1`; the API returns `feature_version: 1`. Existing documents without a version are legacy (version 0), not automatically upgraded. Remeasure to obtain the extra values.

| voice key | Meaning / unit |
|---|---|
| pitchMean | Mean measured F0, Hz; retained for existing consumers. NOT median or semitones. |
| f0Std | Population standard deviation of measured F0, Hz (numpy std, ddof=0). |
| speechRate | Estimated syllable nuclei per second, not STT word count. |
| voicedRatio | Fraction of frames pYIN marks voiced, 0–1. |
| durationSec | Full recording duration in seconds, including silence. |
| energyMean | Mean RMS amplitude; sensitive to microphone/gain/distance, not calibrated across sessions. |

`measuredAt` is UTC ISO-8601. Existing face ratios still come from one image. No multi-frame median or frameCount is claimed. Median pitch, semitone reference and multi-frame face processing remain team discussion items.

The three extra voice fields are saved and returned for downstream analysis. They do not automatically enter the existing Step2 fusion score. In particular recording length is quality/context metadata, not emotion intensity. Downstream weighting and normalization need separate agreement and validation.

```json
{"voice":{"pitchMean":219.9,"f0Std":28.4,"speechRate":4.2,"voicedRatio":0.61,"durationSec":352.0,"energyMean":0.031},"face":{"eyeAspectRatio":0.28,"mouthAspectRatio":0.11,"mouthWidthRatio":1.42,"eyebrowRaiseRatio":0.38},"measuredAt":"2026-09-22T00:00:00+00:00","featureVersion":1}
```

Example values illustrate the schema, not a real user's measurement. Text has no baseline handoff field. Invalid/missing F0 standard deviation or out-of-range voiced ratio is rejected before overwriting a saved baseline.
