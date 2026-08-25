import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/error/app_exception.dart';
import '../../../core/storage/local_store.dart';
import '../../onboarding/application/onboarding_controller.dart';
import '../data/auth_providers.dart';
import '../data/models/app_user.dart';
import '../data/models/social_login_result.dart';
import '../data/repositories/auth_repository.dart';

/// View-facing auth state. Screens watch this; they never touch repositories
/// directly.
class AuthState {
  const AuthState({this.user, this.isLoading = false});

  final AppUser? user;
  final bool isLoading;

  bool get isLoggedIn => user != null;
  bool get onboardingDone => user?.onboardingDone ?? false;

  AuthState copyWith({AppUser? user, bool? isLoading, bool clearUser = false}) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

/// Holds auth state and the login/logout business logic, separate from UI.
///
/// Methods that can fail throw [AuthException]/[NetworkException] with a
/// user-facing message — screens catch and display it.
class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() => const AuthState();

  AuthRepository get _repo => ref.read(authRepositoryProvider);

  /// Splash: restores the saved session. Returns the user, or null when there
  /// is none or "로그인 상태 유지" was unchecked (then the session is discarded).
  Future<AppUser?> restoreSession() async {
    try {
      final user = await _repo.currentUser();
      if (user == null) return null;
      if (!ref.read(localStoreProvider).getBool(LocalStore.kKeepLoggedIn)) {
        await _repo.logout();
        return null;
      }
      _enterSession(user);
      return user;
    } on AppException {
      // A broken saved session should never block the splash → treat as
      // logged out; the user simply logs in again.
      return null;
    }
  }

  Future<void> login({
    required String email,
    required String password,
    required bool keepLoggedIn,
  }) async {
    state = state.copyWith(isLoading: true);
    try {
      final user = await _repo.login(email: email, password: password);
      await ref
          .read(localStoreProvider)
          .setBool(LocalStore.kKeepLoggedIn, keepLoggedIn);
      _enterSession(user);
    } catch (_) {
      state = state.copyWith(isLoading: false);
      rethrow;
    }
  }

  Future<void> signUp({
    required String email,
    required String password,
    required String nickname,
  }) async {
    state = state.copyWith(isLoading: true);
    try {
      final user = await _repo.signUp(
          email: email, password: password, nickname: nickname);
      // A fresh signup stays logged in on this device by default.
      await ref
          .read(localStoreProvider)
          .setBool(LocalStore.kKeepLoggedIn, true);
      _enterSession(user);
    } catch (_) {
      state = state.copyWith(isLoading: false);
      rethrow;
    }
  }

  /// Google sign-in. `success` establishes the session; `needsProfile` means
  /// the caller should route to the extra-info screen (screen 4) and finish
  /// with [completeSocialProfile]; `cancelled` is a no-op.
  Future<SocialLoginStatus> loginWithGoogle() =>
      _socialLogin(_repo.loginWithGoogle);

  /// Kakao sign-in — same semantics as [loginWithGoogle].
  Future<SocialLoginStatus> loginWithKakao() =>
      _socialLogin(_repo.loginWithKakao);

  Future<SocialLoginStatus> _socialLogin(
    Future<SocialLoginResult> Function() attempt,
  ) async {
    state = state.copyWith(isLoading: true);
    try {
      final result = await attempt();
      if (result.status == SocialLoginStatus.success) {
        // Social sign-ins stay logged in on this device by default.
        await ref
            .read(localStoreProvider)
            .setBool(LocalStore.kKeepLoggedIn, true);
        _enterSession(result.user!);
      } else {
        state = state.copyWith(isLoading: false);
      }
      return result.status;
    } catch (_) {
      state = state.copyWith(isLoading: false);
      rethrow;
    }
  }

  /// Finishes a first-time social login by creating the profile.
  Future<void> completeSocialProfile({required String nickname}) async {
    state = state.copyWith(isLoading: true);
    try {
      final user = await _repo.completeSocialProfile(nickname: nickname);
      await ref
          .read(localStoreProvider)
          .setBool(LocalStore.kKeepLoggedIn, true);
      _enterSession(user);
    } catch (_) {
      state = state.copyWith(isLoading: false);
      rethrow;
    }
  }

  Future<void> sendPasswordReset({required String email}) =>
      _repo.sendPasswordReset(email: email);

  /// Updates the nickname on the profile and in the in-memory session.
  Future<void> updateNickname(String nickname) async {
    await _repo.updateNickname(nickname: nickname);
    final user = state.user;
    if (user != null) {
      state = AuthState(user: user.copyWith(nickname: nickname));
    }
  }

  Future<void> logout() async {
    await _repo.logout();
    _leaveSession();
  }

  Future<void> deleteAccount() async {
    await _repo.deleteAccount();
    _leaveSession();
  }

  void _enterSession(AppUser user) {
    state = AuthState(user: user);
    // The home popup branches on this — keep it in sync with the profile.
    ref.read(onboardingCompleteProvider.notifier).set(user.onboardingDone);
  }

  void _leaveSession() {
    state = const AuthState();
    ref.read(onboardingCompleteProvider.notifier).set(false);
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
