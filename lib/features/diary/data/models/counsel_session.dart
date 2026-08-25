/// Who is speaking in a counseling message.
enum CounselSpeaker { oddo, user }

/// A single line in the Step 4 counseling chat log.
class CounselMessage {
  const CounselMessage({required this.speaker, required this.text});

  final CounselSpeaker speaker;
  final String text;

  factory CounselMessage.fromJson(Map<String, dynamic> json) => CounselMessage(
        speaker: CounselSpeaker.values.byName(json['speaker'] as String),
        text: json['text'] as String,
      );

  Map<String, dynamic> toJson() => {
        'speaker': speaker.name,
        'text': text,
      };
}

/// One counseling session attached to a diary date (screen 50).
///
/// Stored at `users/{uid}/counsel_sessions/{yyyy-MM-dd}` — see
/// FIRESTORE_SCHEMA.md.
class CounselSession {
  const CounselSession({
    required this.date,
    required this.startedAt,
    required this.endedAt,
    required this.messages,
  });

  final DateTime date;
  final DateTime startedAt;
  final DateTime endedAt;
  final List<CounselMessage> messages;

  factory CounselSession.fromJson(Map<String, dynamic> json) => CounselSession(
        date: DateTime.parse(json['date'] as String),
        startedAt: DateTime.parse(json['startedAt'] as String),
        endedAt: DateTime.parse(json['endedAt'] as String),
        messages: (json['messages'] as List<dynamic>)
            .map((m) => CounselMessage.fromJson(m as Map<String, dynamic>))
            .toList(),
      );

  Map<String, dynamic> toJson() => {
        'date': date.toIso8601String(),
        'startedAt': startedAt.toIso8601String(),
        'endedAt': endedAt.toIso8601String(),
        'messages': [for (final m in messages) m.toJson()],
      };
}
