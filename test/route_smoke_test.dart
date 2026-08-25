import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:oddo/app/router/app_router.dart';
import 'package:oddo/app/router/app_routes.dart';
import 'package:oddo/core/config/app_config.dart';
import 'package:oddo/core/config/app_config_provider.dart';
import 'package:oddo/core/storage/local_store.dart';
import 'package:oddo/theme/app_theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Every navigable route (the 50 numbered screens minus the 3 modals, plus the
/// auxiliary screens). Modals (login error / baseline-needed / diary-start) are
/// dialogs, not routes, so they're exercised by the widget tests instead.
const _routes = <String>[
  AppPath.splash,
  AppPath.login,
  AppPath.signup,
  AppPath.socialExtraInfo,
  AppPath.findPassword,
  AppPath.termsDetail,
  AppPath.home,
  AppPath.homeWritten,
  AppPath.permission,
  AppPath.tutorialIntro,
  AppPath.tutorialCall,
  AppPath.tutorialSelfIntro,
  AppPath.tutorialVoice,
  AppPath.tutorialFace,
  AppPath.tutorialMethod,
  AppPath.tutorialDone,
  AppPath.baselineIntro,
  AppPath.baselineReady,
  AppPath.baselineMeasuring,
  AppPath.baselineAnalyzing,
  AppPath.baselineDone,
  AppPath.psychTestList,
  AppPath.psychTestStart,
  AppPath.psychTestBig5,
  AppPath.psychTestMbti,
  AppPath.psychTestTendency,
  AppPath.psychTestResume,
  AppPath.psychTestDone,
  AppPath.personaIntro,
  AppPath.personaDetail,
  AppPath.personaDone,
  AppPath.onboardingDone,
  AppPath.monthlyCalendar,
  AppPath.diaryStep1Intro,
  AppPath.diaryStep1Live,
  AppPath.diaryStep1Processing,
  AppPath.diaryStep2Confirm,
  AppPath.diaryStep2Chat,
  AppPath.diaryStep3VideoLoading,
  AppPath.diaryStep3VideoDone,
  AppPath.diaryStep4CounselIntro,
  AppPath.diaryStep4CounselCall,
  AppPath.reportGenerating,
  AppPath.reportGuide,
  AppPath.recordsDiary,
  AppPath.recordsReport,
  AppPath.recordsCounsel,
  AppPath.shortformPlayer,
  AppPath.settings,
  AppPath.myPage,
  AppPath.chatbotSettings,
  AppPath.notifications,
];

/// Tests run on dummy data so they never touch Firebase (also keeps the
/// route guard ungated, so every screen builds directly).
const _testConfig = AppConfig(
  environment: AppEnvironment.dev,
  appName: 'Oddo (test)',
  apiBaseUrl: '',
  useDummyData: true,
);

void main() {
  // Use a realistic phone surface so layout matches the design.
  setUp(() {
    final view = TestWidgetsFlutterBinding.instance.platformDispatcher.views.first;
    view.physicalSize = const Size(1170, 2532);
    view.devicePixelRatio = 3.0;
  });
  tearDown(() {
    final view = TestWidgetsFlutterBinding.instance.platformDispatcher.views.first;
    view.resetPhysicalSize();
    view.resetDevicePixelRatio();
  });

  for (final path in _routes) {
    testWidgets('route builds without error: $path', (tester) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [
          appConfigProvider.overrideWithValue(_testConfig),
          localStoreProvider.overrideWithValue(LocalStore(prefs)),
        ],
      );
      addTearDown(container.dispose);

      final router = container.read(goRouterProvider);
      router.go(path);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            routerConfig: router,
            theme: AppTheme.light,
          ),
        ),
      );
      await tester.pump();

      expect(tester.takeException(), isNull, reason: 'building $path threw');
      expect(find.byType(Scaffold), findsWidgets, reason: 'no Scaffold for $path');

      // Unmount to cancel any auto-advance timers / animations before
      // teardown, then flush non-cancelable delays (e.g. splash restore).
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 2));
    });
  }
}
