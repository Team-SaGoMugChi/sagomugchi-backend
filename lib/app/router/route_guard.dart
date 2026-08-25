import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/app_config_provider.dart';
import '../../features/auth/application/auth_controller.dart';
import 'app_routes.dart';

/// Screens reachable without a session (splash + the auth flow).
const _publicPaths = {
  AppPath.splash,
  AppPath.login,
  AppPath.signup,
  AppPath.socialExtraInfo,
  AppPath.findPassword,
  AppPath.termsDetail, // 가입 중(비로그인) 약관 보기
};

/// Central navigation guard (go_router `redirect`).
///
/// - Dummy-data mode (tests/prototyping) stays ungated so every screen is
///   directly reachable.
/// - Otherwise: no session → only [_publicPaths]; with a session the login and
///   signup screens bounce to home. The splash screen handles the initial
///   session restore itself, so it stays reachable in both states.
String? appRedirect(Ref ref, GoRouterState state) {
  if (ref.read(appConfigProvider).useDummyData) return null;

  final loggedIn = ref.read(authControllerProvider).isLoggedIn;
  final location = state.matchedLocation;

  if (!loggedIn && !_publicPaths.contains(location)) return AppPath.login;
  if (loggedIn && (location == AppPath.login || location == AppPath.signup)) {
    return AppPath.home;
  }
  return null;
}
