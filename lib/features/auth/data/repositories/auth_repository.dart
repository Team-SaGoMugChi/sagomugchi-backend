import '../models/app_user.dart';
import '../models/social_login_result.dart';

/// What the app needs from auth, independent of the data source. The UI/state
/// layer depends only on this interface.
abstract interface class AuthRepository {
  Future<AppUser?> currentUser();

  Future<AppUser> login({required String email, required String password});

  Future<AppUser> signUp({
    required String email,
    required String password,
    required String nickname,
  });

  Future<SocialLoginResult> loginWithGoogle();

  Future<SocialLoginResult> loginWithKakao();

  Future<AppUser> completeSocialProfile({required String nickname});

  Future<void> sendPasswordReset({required String email});

  Future<void> updateOnboardingDone({required bool done});

  Future<void> updateNickname({required String nickname});

  Future<bool> hasPasswordLogin();

  Future<void> logout();

  Future<void> deleteAccount();
}
