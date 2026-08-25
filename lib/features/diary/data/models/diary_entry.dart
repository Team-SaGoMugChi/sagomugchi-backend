/// One day's diary entry, produced by the Step 1–3 write flow.
class DiaryEntry {
  const DiaryEntry({
    required this.id,
    required this.date,
    required this.transcript,
    required this.summary,
    required this.emotionKeywords,
    this.videoUrl,
    this.emotionIntensity = 0,
    this.emotionStability = 0,
    this.writtenAt,
  });

  final String id;
  final DateTime date;

  /// 기록 완료 버튼을 누른 실제 시각 (구버전 문서엔 없을 수 있음).
  final DateTime? writtenAt;

  /// Raw STT text the user reviewed/edited in Step 2.
  final String transcript;

  /// AI-generated summary written in diary style.
  final String summary;

  final List<String> emotionKeywords;

  /// URL/path of the generated short-form video (null until Step 3 finishes).
  final String? videoUrl;

  /// 0–100 scores shown on the Step 2 confirm screen.
  final int emotionIntensity;
  final int emotionStability;

  factory DiaryEntry.fromJson(Map<String, dynamic> json) => DiaryEntry(
        id: json['id'] as String,
        date: DateTime.parse(json['date'] as String),
        transcript: json['transcript'] as String,
        summary: json['summary'] as String,
        emotionKeywords: (json['emotionKeywords'] as List<dynamic>)
            .cast<String>(),
        videoUrl: json['videoUrl'] as String?,
        emotionIntensity: json['emotionIntensity'] as int? ?? 0,
        emotionStability: json['emotionStability'] as int? ?? 0,
        writtenAt: json['writtenAt'] != null
            ? DateTime.parse(json['writtenAt'] as String)
            : null,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date.toIso8601String(),
        'transcript': transcript,
        'summary': summary,
        'emotionKeywords': emotionKeywords,
        'videoUrl': videoUrl,
        'emotionIntensity': emotionIntensity,
        'emotionStability': emotionStability,
        if (writtenAt != null) 'writtenAt': writtenAt!.toIso8601String(),
      };
}
