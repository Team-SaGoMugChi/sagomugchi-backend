import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/data/auth_providers.dart';

/// Whether the user has finished first-run onboarding
/// (튜토리얼 → Baseline 측정 → 심리테스트 → 페르소나 설정).
///
/// Drives the home screen: while `false`, the first-measurement popup auto-opens
/// and the "일기 작성하기" CTA re-opens it; once `true`, the popup is gone and the
/// CTA goes straight to the diary-writing flow.
///
/// The source of truth is `AppUser.onboardingDone` (users/{uid}) — the auth
/// controller calls [set] with it on login/session restore, and [markComplete]
/// writes it back to the profile.
class OnboardingController extends Notifier<bool> {
  @override
  bool build() => false;

  /// Synced from the logged-in user's profile (login / session restore).
  void set(bool done) => state = done;

  void markComplete() {
    state = true;
    // Best-effort persist on the profile; a failure only means the popup could
    // reappear on a later fresh login.
    unawaited(
      ref
          .read(authRepositoryProvider)
          .updateOnboardingDone(done: true)
          .catchError((_) {}),
    );
  }
}

final onboardingCompleteProvider =
    NotifierProvider<OnboardingController, bool>(OnboardingController.new);
