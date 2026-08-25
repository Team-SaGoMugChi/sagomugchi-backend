import '../models/app_user.dart';
import '../models/social_login_result.dart';

/// Abstraction over where auth data comes from. A dummy implementation backs
/// tests/prototyping; the Firebase implementation is the real one.
///
/// Implementations throw `AuthException` (user-facing Korean message) or
/// `NetworkException` — never provider-specific exception types.
abstract interface class AuthDataSource {
  /// The saved session's user, or null when signed out.
  Future<AppUser?> currentUser();

  Future<AppUser> login({required String email, required String password});

  Future<AppUser> signUp({
    required String email,
    required String password,
    required String nickname,
  });

  /// Google sign-in. `needsProfile` means the account is authenticated but has
  /// no profile yet — follow with [completeSocialProfile].
  Future<SocialLoginResult> loginWithGoogle();

  /// Kakao sign-in (KakaoTalk app jump, falls back to Kakao-account web
  /// login). Same result semantics as [loginWithGoogle].
  Future<SocialLoginResult> loginWithKakao();

  /// Creates the `users/{uid}` profile for a first-time social user.
  Future<AppUser> completeSocialProfile({required String nickname});

  Future<void> sendPasswordReset({required String email});

  /// Persists onboarding completion on the user profile.
  Future<void> updateOnboardingDone({required bool done});

  /// Updates the profile nickname.
  Future<void> updateNickname({required String nickname});

  /// True when this account can change its password (email/password login).
  /// Social-only accounts (Google/Kakao) return false.
  Future<bool> hasPasswordLogin();

  Future<void> logout();

  /// Permanently deletes the account and its profile data.
  Future<void> deleteAccount();
}
