/// Post-counseling emotion report + behavior guide for a given date
/// (screens 46 / 49).
///
/// Stored at `users/{uid}/reports/{yyyy-MM-dd}` — see FIRESTORE_SCHEMA.md.
class EmotionReport {
  const EmotionReport({
    required this.date,
    required this.emotionDistribution,
    required this.emotionIntensity,
    required this.recoveryPossibility,
    required this.analysisComment,
    required this.behaviorGuides,
    required this.recommendedActivities,
  });

  final DateTime date;

  /// Emotion → share (0–1), e.g. {'속상함': 0.42, '후회': 0.28, ...}.
  final Map<String, double> emotionDistribution;

  final int emotionIntensity; // 0–100
  final int recoveryPossibility; // 0–100
  final String analysisComment;
  final List<String> behaviorGuides;
  final List<String> recommendedActivities;

  factory EmotionReport.fromJson(Map<String, dynamic> json) => EmotionReport(
        date: DateTime.parse(json['date'] as String),
        emotionDistribution:
            (json['emotionDistribution'] as Map<String, dynamic>)
                .map((k, v) => MapEntry(k, (v as num).toDouble())),
        emotionIntensity: json['emotionIntensity'] as int? ?? 0,
        recoveryPossibility: json['recoveryPossibility'] as int? ?? 0,
        analysisComment: json['analysisComment'] as String,
        behaviorGuides:
            (json['behaviorGuides'] as List<dynamic>).cast<String>(),
        recommendedActivities:
            (json['recommendedActivities'] as List<dynamic>).cast<String>(),
      );

  Map<String, dynamic> toJson() => {
        'date': date.toIso8601String(),
        'emotionDistribution': emotionDistribution,
        'emotionIntensity': emotionIntensity,
        'recoveryPossibility': recoveryPossibility,
        'analysisComment': analysisComment,
        'behaviorGuides': behaviorGuides,
        'recommendedActivities': recommendedActivities,
      };
}
