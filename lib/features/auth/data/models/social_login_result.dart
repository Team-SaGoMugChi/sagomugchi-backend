import 'app_user.dart';

/// How a social (Google/…) sign-in attempt ended.
enum SocialLoginStatus {
  /// Existing user — session established, go home.
  success,

  /// Account authenticated but no `users/{uid}` profile yet — collect the
  /// extra info (screen 4) then call `completeSocialProfile`.
  needsProfile,

  /// The user closed the account-picker; not an error.
  cancelled,
}

class SocialLoginResult {
  const SocialLoginResult(this.status, [this.user]);

  final SocialLoginStatus status;

  /// Set only when [status] is [SocialLoginStatus.success].
  final AppUser? user;
}
