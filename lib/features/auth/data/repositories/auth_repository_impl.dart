import '../datasources/auth_data_source.dart';
import '../models/app_user.dart';
import '../models/social_login_result.dart';
import 'auth_repository.dart';

/// Default repository — delegates to a [AuthDataSource]. Data sources already
/// normalize provider errors to `AuthException`/`NetworkException`, so this
/// stays a thin pass-through until multiple sources need combining.
class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl(this._dataSource);

  final AuthDataSource _dataSource;

  @override
  Future<AppUser?> currentUser() => _dataSource.currentUser();

  @override
  Future<AppUser> login({required String email, required String password}) =>
      _dataSource.login(email: email, password: password);

  @override
  Future<AppUser> signUp({
    required String email,
    required String password,
    required String nickname,
  }) =>
      _dataSource.signUp(email: email, password: password, nickname: nickname);

  @override
  Future<SocialLoginResult> loginWithGoogle() => _dataSource.loginWithGoogle();

  @override
  Future<SocialLoginResult> loginWithKakao() => _dataSource.loginWithKakao();

  @override
  Future<AppUser> completeSocialProfile({required String nickname}) =>
      _dataSource.completeSocialProfile(nickname: nickname);

  @override
  Future<void> sendPasswordReset({required String email}) =>
      _dataSource.sendPasswordReset(email: email);

  @override
  Future<void> updateOnboardingDone({required bool done}) =>
      _dataSource.updateOnboardingDone(done: done);

  @override
  Future<void> updateNickname({required String nickname}) =>
      _dataSource.updateNickname(nickname: nickname);

  @override
  Future<bool> hasPasswordLogin() => _dataSource.hasPasswordLogin();

  @override
  Future<void> logout() => _dataSource.logout();

  @override
  Future<void> deleteAccount() => _dataSource.deleteAccount();
}
