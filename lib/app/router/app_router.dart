import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/dummy/terms_dummy.dart';
import '../../features/auth/presentation/screens/find_password_screen.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/auth/presentation/screens/signup_screen.dart';
import '../../features/auth/presentation/screens/social_extra_info_screen.dart';
import '../../features/auth/presentation/screens/splash_screen.dart';
import '../../features/auth/presentation/screens/terms_detail_screen.dart';
import '../../features/baseline/presentation/screens/baseline_analyzing_screen.dart';
import '../../features/baseline/presentation/screens/baseline_done_screen.dart';
import '../../features/baseline/presentation/screens/baseline_intro_screen.dart';
import '../../features/baseline/presentation/screens/baseline_measuring_screen.dart';
import '../../features/baseline/presentation/screens/baseline_ready_screen.dart';
import '../../features/calendar/presentation/screens/monthly_calendar_screen.dart';
import '../../features/diary/presentation/screens/diary_step1_intro_screen.dart';
import '../../features/diary/presentation/screens/diary_step1_live_screen.dart';
import '../../features/diary/presentation/screens/diary_step1_processing_screen.dart';
import '../../features/diary/presentation/screens/diary_step2_chat_screen.dart';
import '../../features/diary/presentation/screens/diary_step2_confirm_screen.dart';
import '../../features/diary/presentation/screens/diary_step3_video_done_screen.dart';
import '../../features/diary/presentation/screens/diary_step3_video_loading_screen.dart';
import '../../features/diary/presentation/screens/diary_step4_counsel_call_screen.dart';
import '../../features/diary/presentation/screens/diary_step4_counsel_intro_screen.dart';
import '../../features/diary/presentation/screens/report_generating_screen.dart';
import '../../features/diary/presentation/screens/report_guide_screen.dart';
import '../../features/home/presentation/screens/home_screen.dart';
import '../../features/notifications/presentation/screens/notifications_screen.dart';
import '../../features/onboarding/presentation/screens/onboarding_done_screen.dart';
import '../../features/onboarding/presentation/screens/permission_screen.dart';
import '../../features/persona/presentation/screens/persona_detail_screen.dart';
import '../../features/persona/presentation/screens/persona_done_screen.dart';
import '../../features/persona/presentation/screens/persona_intro_screen.dart';
import '../../features/psych_test/presentation/screens/big5_screen.dart';
import '../../features/psych_test/presentation/screens/mbti_screen.dart';
import '../../features/psych_test/presentation/screens/psych_test_done_screen.dart';
import '../../features/psych_test/presentation/screens/psych_test_list_screen.dart';
import '../../features/psych_test/presentation/screens/psych_test_resume_screen.dart';
import '../../features/psych_test/presentation/screens/psych_test_start_screen.dart';
import '../../features/psych_test/presentation/screens/tendency_screen.dart';
import '../../features/records/presentation/records_shell.dart';
import '../../features/records/presentation/screens/counsel_record_screen.dart';
import '../../features/records/presentation/screens/diary_detail_screen.dart';
import '../../features/records/presentation/screens/emotion_report_screen.dart';
import '../../features/records/presentation/screens/shortform_player_screen.dart';
import '../../features/settings/presentation/screens/chatbot_settings_screen.dart';
import '../../features/settings/presentation/screens/my_page_screen.dart';
import '../../features/settings/presentation/screens/settings_home_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_call_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_done_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_face_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_intro_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_method_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_self_intro_screen.dart';
import '../../features/tutorial/presentation/screens/tutorial_voice_screen.dart';
import 'app_routes.dart';
import 'route_guard.dart';

/// Root navigator key (the app's outermost navigator).
final _rootNavigatorKey = GlobalKey<NavigatorState>();

/// The single, app-wide [GoRouter], exposed via Riverpod so it can read other
/// providers (auth, config) for redirects later. All screens live here; the
/// written-day records context is a [StatefulShellRoute].
final goRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: AppPath.splash,
    debugLogDiagnostics: true,
    redirect: (context, state) => appRedirect(ref, state),
    routes: [
      // ── Auth ──────────────────────────────────────────────────────────
      GoRoute(
        path: AppPath.splash,
        name: AppRoute.splash,
        builder: (_, _) => const SplashScreen(),
      ),
      GoRoute(
        path: AppPath.login,
        name: AppRoute.login,
        builder: (_, _) => const LoginScreen(),
      ),
      GoRoute(
        path: AppPath.signup,
        name: AppRoute.signup,
        builder: (_, _) => const SignupScreen(),
      ),
      GoRoute(
        path: AppPath.socialExtraInfo,
        name: AppRoute.socialExtraInfo,
        builder: (_, _) => const SocialExtraInfoScreen(),
      ),
      GoRoute(
        path: AppPath.findPassword,
        name: AppRoute.findPassword,
        builder: (_, _) => const FindPasswordScreen(),
      ),
      GoRoute(
        path: AppPath.termsDetail,
        name: AppRoute.termsDetail,
        // extra로 TermsDoc 전달; 없으면(딥링크 등) 첫 문서 표시.
        builder: (_, state) => TermsDetailScreen(
          doc: state.extra is TermsDoc
              ? state.extra as TermsDoc
              : TermsDummy.docs.first,
        ),
      ),

      // ── Home ──────────────────────────────────────────────────────────
      GoRoute(
        path: AppPath.home,
        name: AppRoute.home,
        builder: (_, _) => const HomeScreen(),
      ),
      GoRoute(
        path: AppPath.homeWritten,
        name: AppRoute.homeWritten,
        builder: (_, _) => const HomeScreen(),
      ),

      // ── Onboarding: permission ──────────────────────────────────────────
      GoRoute(
        path: AppPath.permission,
        name: AppRoute.permission,
        builder: (_, _) => const PermissionScreen(),
      ),

      // ── Onboarding: tutorial ────────────────────────────────────────────
      GoRoute(
        path: AppPath.tutorialIntro,
        name: AppRoute.tutorialIntro,
        builder: (_, _) => const TutorialIntroScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialCall,
        name: AppRoute.tutorialCall,
        builder: (_, _) => const TutorialCallScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialSelfIntro,
        name: AppRoute.tutorialSelfIntro,
        builder: (_, _) => const TutorialSelfIntroScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialVoice,
        name: AppRoute.tutorialVoice,
        builder: (_, _) => const TutorialVoiceScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialFace,
        name: AppRoute.tutorialFace,
        builder: (_, _) => const TutorialFaceScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialMethod,
        name: AppRoute.tutorialMethod,
        builder: (_, _) => const TutorialMethodScreen(),
      ),
      GoRoute(
        path: AppPath.tutorialDone,
        name: AppRoute.tutorialDone,
        builder: (_, _) => const TutorialDoneScreen(),
      ),

      // ── Onboarding: baseline ────────────────────────────────────────────
      GoRoute(
        path: AppPath.baselineIntro,
        name: AppRoute.baselineIntro,
        builder: (_, _) => const BaselineIntroScreen(),
      ),
      GoRoute(
        path: AppPath.baselineReady,
        name: AppRoute.baselineReady,
        builder: (_, _) => const BaselineReadyScreen(),
      ),
      GoRoute(
        path: AppPath.baselineMeasuring,
        name: AppRoute.baselineMeasuring,
        builder: (_, _) => const BaselineMeasuringScreen(),
      ),
      GoRoute(
        path: AppPath.baselineAnalyzing,
        name: AppRoute.baselineAnalyzing,
        builder: (_, _) => const BaselineAnalyzingScreen(),
      ),
      GoRoute(
        path: AppPath.baselineDone,
        name: AppRoute.baselineDone,
        builder: (_, _) => const BaselineDoneScreen(),
      ),

      // ── Onboarding: psych test ──────────────────────────────────────────
      GoRoute(
        path: AppPath.psychTestList,
        name: AppRoute.psychTestList,
        builder: (_, _) => const PsychTestListScreen(),
      ),
      GoRoute(
        path: AppPath.psychTestStart,
        name: AppRoute.psychTestStart,
        builder: (_, _) => const PsychTestStartScreen(),
      ),
      GoRoute(
        path: AppPath.psychTestBig5,
        name: AppRoute.psychTestBig5,
        builder: (_, _) => const Big5Screen(),
      ),
      GoRoute(
        path: AppPath.psychTestMbti,
        name: AppRoute.psychTestMbti,
        builder: (_, _) => const MbtiScreen(),
      ),
      GoRoute(
        path: AppPath.psychTestTendency,
        name: AppRoute.psychTestTendency,
        builder: (_, _) => const TendencyScreen(),
      ),
      GoRoute(
        path: AppPath.psychTestResume,
        name: AppRoute.psychTestResume,
        builder: (_, _) => const PsychTestResumeScreen(),
      ),
      GoRoute(
        path: AppPath.psychTestDone,
        name: AppRoute.psychTestDone,
        builder: (_, _) => const PsychTestDoneScreen(),
      ),

      // ── Onboarding: persona + done ──────────────────────────────────────
      GoRoute(
        path: AppPath.personaIntro,
        name: AppRoute.personaIntro,
        builder: (_, _) => const PersonaIntroScreen(),
      ),
      GoRoute(
        path: AppPath.personaDetail,
        name: AppRoute.personaDetail,
        builder: (_, _) => const PersonaDetailScreen(),
      ),
      GoRoute(
        path: AppPath.personaDone,
        name: AppRoute.personaDone,
        builder: (_, _) => const PersonaDoneScreen(),
      ),
      GoRoute(
        path: AppPath.onboardingDone,
        name: AppRoute.onboardingDone,
        builder: (_, _) => const OnboardingDoneScreen(),
      ),

      // ── Calendar ────────────────────────────────────────────────────────
      GoRoute(
        path: AppPath.monthlyCalendar,
        name: AppRoute.monthlyCalendar,
        builder: (_, _) => const MonthlyCalendarScreen(),
      ),

      // ── Diary write flow ────────────────────────────────────────────────
      GoRoute(
        path: AppPath.diaryStep1Intro,
        name: AppRoute.diaryStep1Intro,
        builder: (_, _) => const DiaryStep1IntroScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep1Live,
        name: AppRoute.diaryStep1Live,
        builder: (_, _) => const DiaryStep1LiveScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep1Processing,
        name: AppRoute.diaryStep1Processing,
        builder: (_, _) => const DiaryStep1ProcessingScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep2Confirm,
        name: AppRoute.diaryStep2Confirm,
        builder: (_, _) => const DiaryStep2ConfirmScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep2Chat,
        name: AppRoute.diaryStep2Chat,
        builder: (_, _) => const DiaryStep2ChatScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep3VideoLoading,
        name: AppRoute.diaryStep3VideoLoading,
        builder: (_, _) => const DiaryStep3VideoLoadingScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep3VideoDone,
        name: AppRoute.diaryStep3VideoDone,
        builder: (_, _) => const DiaryStep3VideoDoneScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep4CounselIntro,
        name: AppRoute.diaryStep4CounselIntro,
        builder: (_, _) => const DiaryStep4CounselIntroScreen(),
      ),
      GoRoute(
        path: AppPath.diaryStep4CounselCall,
        name: AppRoute.diaryStep4CounselCall,
        builder: (_, _) => const DiaryStep4CounselCallScreen(),
      ),
      GoRoute(
        path: AppPath.reportGenerating,
        name: AppRoute.reportGenerating,
        builder: (_, _) => const ReportGeneratingScreen(),
      ),
      GoRoute(
        path: AppPath.reportGuide,
        name: AppRoute.reportGuide,
        builder: (_, _) => const ReportGuideScreen(),
      ),

      // ── Auxiliary ───────────────────────────────────────────────────────
      GoRoute(
        path: AppPath.shortformPlayer,
        name: AppRoute.shortformPlayer,
        builder: (_, _) => const ShortformPlayerScreen(),
      ),
      GoRoute(
        path: AppPath.settings,
        name: AppRoute.settings,
        builder: (_, _) => const SettingsHomeScreen(),
      ),
      GoRoute(
        path: AppPath.myPage,
        name: AppRoute.myPage,
        builder: (_, _) => const MyPageScreen(),
      ),
      GoRoute(
        path: AppPath.chatbotSettings,
        name: AppRoute.chatbotSettings,
        builder: (_, _) => const ChatbotSettingsScreen(),
      ),
      GoRoute(
        path: AppPath.notifications,
        name: AppRoute.notifications,
        builder: (_, _) => const NotificationsScreen(),
      ),

      // ── Records (written-day context with [일기][리포트][상담] tab bar) ──
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            RecordsShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppPath.recordsDiary,
                name: AppRoute.recordsDiary,
                builder: (_, _) => const DiaryDetailScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppPath.recordsReport,
                name: AppRoute.recordsReport,
                builder: (_, _) => const EmotionReportScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppPath.recordsCounsel,
                name: AppRoute.recordsCounsel,
                builder: (_, _) => const CounselRecordScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(child: Text('경로를 찾을 수 없어요: ${state.uri}')),
    ),
  );

  ref.onDispose(router.dispose);
  return router;
});
