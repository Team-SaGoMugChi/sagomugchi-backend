/// The user's face/voice baseline, measured once during onboarding and used
/// as the comparison reference for every diary's emotion analysis.
///
/// Stored at `users/{uid}/meta/baseline` — see FIRESTORE_SCHEMA.md.
///
/// [voice]/[face] keys are defined by the AI server (Phase 4) — e.g.
/// `pitchMean`, `speechRate`, `energyMean` — the app only stores and forwards
/// them without interpreting.
class BaselineProfile {
  const BaselineProfile({
    required this.voice,
    required this.face,
    required this.measuredAt,
  });

  final Map<String, double> voice;
  final Map<String, double> face;
  final DateTime measuredAt;

  factory BaselineProfile.fromJson(Map<String, dynamic> json) =>
      BaselineProfile(
        voice: (json['voice'] as Map<String, dynamic>? ?? {})
            .map((k, v) => MapEntry(k, (v as num).toDouble())),
        face: (json['face'] as Map<String, dynamic>? ?? {})
            .map((k, v) => MapEntry(k, (v as num).toDouble())),
        measuredAt: DateTime.parse(json['measuredAt'] as String),
      );

  Map<String, dynamic> toJson() => {
        'voice': voice,
        'face': face,
        'measuredAt': measuredAt.toIso8601String(),
      };
}
