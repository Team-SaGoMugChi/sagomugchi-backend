/// A chatbot tone option (말투) on the persona detail screen.
class PersonaTone {
  const PersonaTone(this.title, this.description);
  final String title;
  final String description;
}

/// Static dummy content for the chatbot-persona setup. Mirrors the mockups and
/// `_docs/02`. The detail screen's selections are local UI state for the
/// prototype; the default values below feed the completion summary.
abstract final class PersonaDummy {
  PersonaDummy._();

  /// 말투 선택 (single-select).
  static const List<PersonaTone> tones = [
    PersonaTone('친근하고 따뜻한', '부드럽고 친근하게, 일상 속 친구처럼 편하게 대화해요.'),
    PersonaTone('차분하고 진중한', '신중하고 차분하게 깊이 있는 생각을 나눠요.'),
    PersonaTone('밝고 에너지 넘치는', '긍정적이고 활기차게 기분을 북돋아줘요.'),
    PersonaTone('간결하고 솔직한', '군더더기 없이 솔직하고 명확하게 이야기해요.'),
  ];

  /// 성격 선택 (multi-select chips).
  static const List<String> traits = [
    '공감 잘해주는',
    '조언을 잘해주는',
    '유머러스한',
    '신중한',
    '따뜻한',
    '현실적인',
  ];

  static const String nameHint = '이름을 입력해주세요. 예: 오드, 나의 친구 등';
  static const int nameMaxLength = 10;

  // Default selections (also shown on the completion summary, screen 31).
  static const String defaultName = '오디';
  static const String defaultTone = '친근하고 따뜻한';
  static const List<String> defaultTraits = ['공감 잘해주는', '따뜻한'];

  /// 32 — onboarding completion summary.
  static const List<String> onboardingSummary = [
    '첫 측정 완료',
    '심리테스트 완료',
    '페르소나 설정 완료',
  ];
}
