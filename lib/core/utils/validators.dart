/// Form-input validators shared by the auth screens. Each returns a
/// user-facing error message, or null when the value is valid.
abstract final class Validators {
  Validators._();

  static final RegExp _emailRe = RegExp(r'^[\w.+-]+@[\w-]+\.[\w.-]+$');

  static String? email(String value) {
    final v = value.trim();
    if (v.isEmpty) return '이메일을 입력해주세요.';
    if (!_emailRe.hasMatch(v)) return '이메일 형식이 올바르지 않아요.';
    return null;
  }

  /// Matches Firebase's 6-character minimum.
  static String? password(String value) {
    if (value.isEmpty) return '비밀번호를 입력해주세요.';
    if (value.length < 6) return '비밀번호는 6자 이상이어야 해요.';
    return null;
  }

  static String? passwordConfirm(String value, String original) {
    if (value.isEmpty) return '비밀번호를 한 번 더 입력해주세요.';
    if (value != original) return '비밀번호가 서로 달라요.';
    return null;
  }

  static String? nickname(String value) {
    final v = value.trim();
    if (v.isEmpty) return '닉네임을 입력해주세요.';
    if (v.length > 10) return '닉네임은 10자 이하로 입력해주세요.';
    return null;
  }
}
