/// A single consent item shown in the terms-agreement section.
class TermItem {
  const TermItem(this.title, {this.required = false});

  final String title;
  final bool required;
}

/// Static dummy content for the auth/onboarding forms. Copy mirrors the
/// mockups and `_docs/02_관련_화면_설명_및_이동_흐름.md`. Swap for real,
/// localized content later.
abstract final class AuthDummy {
  AuthDummy._();

  // Field hints.
  static const String emailHint = '이메일을 입력해주세요';
  static const String passwordHint = '비밀번호를 입력해주세요';
  static const String passwordConfirmHint = '비밀번호를 다시 입력해주세요';
  static const String nicknameHint = '닉네임을 입력해주세요';
  static const String birthHint = 'YYYY.MM.DD';

  /// Gender options (회원가입 / 추가 정보 입력).
  static const List<String> genders = ['여성', '남성', '선택 안 함'];

  /// Consent items (전체 동의 + list). Order matches the mockups.
  static const List<TermItem> terms = [
    TermItem('서비스 이용약관', required: true),
    TermItem('개인정보 처리방침', required: true),
    TermItem('감정 분석 데이터 활용 동의', required: true),
    TermItem('마케팅 정보 수신 동의'),
  ];
}
