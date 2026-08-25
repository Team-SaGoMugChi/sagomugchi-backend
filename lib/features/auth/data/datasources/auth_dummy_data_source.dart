import '../../../../core/constants/app_durations.dart';
import '../../../../data/dummy/dummy_seed.dart';
import '../models/app_user.dart';
import '../models/social_login_result.dart';
import 'auth_data_source.dart';

/// In-memory auth backed by [DummySeed]. Simulates latency so loading states
/// behave like the real thing. (Session check is instant, like the real one.)
class AuthDummyDataSource implements AuthDataSource {
  AppUser? _current;

  Future<void> _delay() => Future<void>.delayed(AppDurations.dummyLatency);

  @override
  Future<AppUser?> currentUser() async => _current;

  @override
  Future<AppUser> login({
    required String email,
    required String password,
  }) async {
    await _delay();
    _current = DummySeed.user;
    return _current!;
  }

  @override
  Future<AppUser> signUp({
    required String email,
    required String password,
    required String nickname,
  }) async {
    await _delay();
    _current = DummySeed.user.copyWith(
      email: email,
      nickname: nickname,
      onboardingDone: false,
    );
    return _current!;
  }

  @override
  Future<SocialLoginResult> loginWithGoogle() async {
    await _delay();
    _current = DummySeed.user;
    return SocialLoginResult(SocialLoginStatus.success, _current);
  }

  @override
  Future<SocialLoginResult> loginWithKakao() async {
    await _delay();
    _current = DummySeed.user;
    return SocialLoginResult(SocialLoginStatus.success, _current);
  }

  @override
  Future<AppUser> completeSocialProfile({required String nickname}) async {
    await _delay();
    _current = DummySeed.user.copyWith(nickname: nickname, onboardingDone: false);
    return _current!;
  }

  @override
  Future<void> sendPasswordReset({required String email}) => _delay();

  @override
  Future<void> updateOnboardingDone({required bool done}) async {
    _current = _current?.copyWith(onboardingDone: done);
  }

  @override
  Future<void> updateNickname({required String nickname}) async {
    await _delay();
    _current = _current?.copyWith(nickname: nickname);
  }

  @override
  Future<bool> hasPasswordLogin() async => true;

  @override
  Future<void> logout() async {
    await _delay();
    _current = null;
  }

  @override
  Future<void> deleteAccount() async {
    await _delay();
    _current = null;
  }
}
