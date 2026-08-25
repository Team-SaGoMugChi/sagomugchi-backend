/// Results of the onboarding psych tests (Big5 / MBTI / 성향).
///
/// Stored at `users/{uid}/meta/psych` — see FIRESTORE_SCHEMA.md.
///
/// Each section is null until that test is finished, which is also how the
/// resume screen (27) decides an in-progress state: some — but not all —
/// sections present.
class PsychResult {
  const PsychResult({
    this.big5,
    this.mbti,
    this.tendencyTraits,
    required this.updatedAt,
  });

  /// O/C/E/A/N trait → 0–100 score.
  final Map<String, int>? big5;

  /// e.g. 'INFP'.
  final String? mbti;

  /// Tags produced by the 성향 test.
  final List<String>? tendencyTraits;

  final DateTime updatedAt;

  /// All three tests finished (screen 28 완료 state).
  bool get isComplete => big5 != null && mbti != null && tendencyTraits != null;

  PsychResult copyWith({
    Map<String, int>? big5,
    String? mbti,
    List<String>? tendencyTraits,
    DateTime? updatedAt,
  }) {
    return PsychResult(
      big5: big5 ?? this.big5,
      mbti: mbti ?? this.mbti,
      tendencyTraits: tendencyTraits ?? this.tendencyTraits,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory PsychResult.fromJson(Map<String, dynamic> json) => PsychResult(
        big5: (json['big5'] as Map<String, dynamic>?)
            ?.map((k, v) => MapEntry(k, v as int)),
        mbti: json['mbti'] as String?,
        tendencyTraits:
            (json['tendencyTraits'] as List<dynamic>?)?.cast<String>(),
        updatedAt: DateTime.parse(json['updatedAt'] as String),
      );

  Map<String, dynamic> toJson() => {
        if (big5 != null) 'big5': big5,
        if (mbti != null) 'mbti': mbti,
        if (tendencyTraits != null) 'tendencyTraits': tendencyTraits,
        'updatedAt': updatedAt.toIso8601String(),
      };
}
