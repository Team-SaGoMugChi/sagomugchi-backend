/// Single source of truth for every route's **name** and **path**.
///
/// Navigate by name everywhere (`context.goNamed(AppRoute.home)`), so paths can
/// change without touching call sites. Paths are grouped to mirror the app's
/// flows. Numbers in comments map to the screen list in
/// `_docs/01_전체_페이지_흐름.md`.
abstract final class AppRoute {
  AppRoute._();

  // ── Auth (1–6) ─────────────────────────────────────────────────────────
  static const String splash = 'splash'; // 1
  static const String login = 'login'; // 2
  static const String signup = 'signup'; // 3
  static const String socialExtraInfo = 'socialExtraInfo'; // 4
  // 5 로그인 실패 모달 → dialog (see auth feature), not a route
  static const String findPassword = 'findPassword'; // 6
  static const String termsDetail = 'termsDetail'; // 약관 뷰어 (보조)

  // ── Home (7, 47) ─────────────────────────────────────────────────────────
  static const String home = 'home'; // 7 미작성일
  static const String homeWritten = 'homeWritten'; // 47 작성일
  // 8 Baseline 측정 필요 팝업 → bottom sheet, not a route

  // ── Onboarding: permission (9) ───────────────────────────────────────────
  static const String permission = 'permission'; // 9

  // ── Onboarding: tutorial (10–16) ─────────────────────────────────────────
  static const String tutorialIntro = 'tutorialIntro'; // 10 (1/5)
  static const String tutorialCall = 'tutorialCall'; // 11 통화 연습
  static const String tutorialSelfIntro = 'tutorialSelfIntro'; // 12 (2/5)
  static const String tutorialVoice = 'tutorialVoice'; // 13 (3/5)
  static const String tutorialFace = 'tutorialFace'; // 14 (4/5)
  static const String tutorialMethod = 'tutorialMethod'; // 15 (5/5)
  static const String tutorialDone = 'tutorialDone'; // 16

  // ── Onboarding: baseline (17–21) ─────────────────────────────────────────
  static const String baselineIntro = 'baselineIntro'; // 17
  static const String baselineReady = 'baselineReady'; // 18
  static const String baselineMeasuring = 'baselineMeasuring'; // 19
  static const String baselineAnalyzing = 'baselineAnalyzing'; // 20
  static const String baselineDone = 'baselineDone'; // 21

  // ── Onboarding: psych test (22–28) ───────────────────────────────────────
  static const String psychTestList = 'psychTestList'; // 22
  static const String psychTestStart = 'psychTestStart'; // 23
  static const String psychTestBig5 = 'psychTestBig5'; // 24
  static const String psychTestMbti = 'psychTestMbti'; // 25
  static const String psychTestTendency = 'psychTestTendency'; // 26
  static const String psychTestResume = 'psychTestResume'; // 27
  static const String psychTestDone = 'psychTestDone'; // 28

  // ── Onboarding: persona (29–32) ──────────────────────────────────────────
  static const String personaIntro = 'personaIntro'; // 29
  static const String personaDetail = 'personaDetail'; // 30
  static const String personaDone = 'personaDone'; // 31
  static const String onboardingDone = 'onboardingDone'; // 32

  // ── Calendar (33/34) ─────────────────────────────────────────────────────
  static const String monthlyCalendar = 'monthlyCalendar'; // 33/34
  // 35 일기 작성 시작 확인 모달 → dialog, not a route

  // ── Diary write flow (36–46) ─────────────────────────────────────────────
  static const String diaryStep1Intro = 'diaryStep1Intro'; // 36
  static const String diaryStep1Live = 'diaryStep1Live'; // 37
  static const String diaryStep1Processing = 'diaryStep1Processing'; // 38
  static const String diaryStep2Confirm = 'diaryStep2Confirm'; // 39
  static const String diaryStep2Chat = 'diaryStep2Chat'; // 40
  static const String diaryStep3VideoLoading = 'diaryStep3VideoLoading'; // 41
  static const String diaryStep3VideoDone = 'diaryStep3VideoDone'; // 42
  static const String diaryStep4CounselIntro = 'diaryStep4CounselIntro'; // 43
  static const String diaryStep4CounselCall = 'diaryStep4CounselCall'; // 44
  static const String reportGenerating = 'reportGenerating'; // 45
  static const String reportGuide = 'reportGuide'; // 46 감정 리포트·행동 가이드

  // ── Records (written-day shell, 48–50) ───────────────────────────────────
  // Shown only in the written-day context with the [일기][리포트][상담] tab bar.
  static const String recordsDiary = 'recordsDiary'; // 48 일기 상세
  static const String recordsReport = 'recordsReport'; // 49 감정 리포트
  static const String recordsCounsel = 'recordsCounsel'; // 50 상담 기록

  // ── Auxiliary (referenced by flows, not in the numbered list) ────────────
  static const String shortformPlayer = 'shortformPlayer'; // 숏폼 전체화면
  static const String settings = 'settings'; // 설정 홈
  static const String myPage = 'myPage'; // 마이페이지
  static const String chatbotSettings = 'chatbotSettings'; // 챗봇 설정
  static const String notifications = 'notifications'; // 알림 목록
}

/// Path strings, kept separate from names. Only the router reads these.
abstract final class AppPath {
  AppPath._();

  static const String splash = '/';
  static const String login = '/login';
  static const String signup = '/signup';
  static const String socialExtraInfo = '/social-extra-info';
  static const String findPassword = '/find-password';
  static const String termsDetail = '/terms';

  static const String home = '/home';
  static const String homeWritten = '/home/written';

  static const String permission = '/onboarding/permission';

  static const String tutorialIntro = '/onboarding/tutorial/intro';
  static const String tutorialCall = '/onboarding/tutorial/call';
  static const String tutorialSelfIntro = '/onboarding/tutorial/self-intro';
  static const String tutorialVoice = '/onboarding/tutorial/voice';
  static const String tutorialFace = '/onboarding/tutorial/face';
  static const String tutorialMethod = '/onboarding/tutorial/method';
  static const String tutorialDone = '/onboarding/tutorial/done';

  static const String baselineIntro = '/onboarding/baseline/intro';
  static const String baselineReady = '/onboarding/baseline/ready';
  static const String baselineMeasuring = '/onboarding/baseline/measuring';
  static const String baselineAnalyzing = '/onboarding/baseline/analyzing';
  static const String baselineDone = '/onboarding/baseline/done';

  static const String psychTestList = '/onboarding/psych-test/list';
  static const String psychTestStart = '/onboarding/psych-test/start';
  static const String psychTestBig5 = '/onboarding/psych-test/big5';
  static const String psychTestMbti = '/onboarding/psych-test/mbti';
  static const String psychTestTendency = '/onboarding/psych-test/tendency';
  static const String psychTestResume = '/onboarding/psych-test/resume';
  static const String psychTestDone = '/onboarding/psych-test/done';

  static const String personaIntro = '/onboarding/persona/intro';
  static const String personaDetail = '/onboarding/persona/detail';
  static const String personaDone = '/onboarding/persona/done';
  static const String onboardingDone = '/onboarding/done';

  static const String monthlyCalendar = '/calendar';

  static const String diaryStep1Intro = '/diary/write/step1/intro';
  static const String diaryStep1Live = '/diary/write/step1/live';
  static const String diaryStep1Processing = '/diary/write/step1/processing';
  static const String diaryStep2Confirm = '/diary/write/step2/confirm';
  static const String diaryStep2Chat = '/diary/write/step2/chat';
  static const String diaryStep3VideoLoading = '/diary/write/step3/loading';
  static const String diaryStep3VideoDone = '/diary/write/step3/done';
  static const String diaryStep4CounselIntro = '/diary/write/step4/intro';
  static const String diaryStep4CounselCall = '/diary/write/step4/call';
  static const String reportGenerating = '/diary/write/report-generating';
  static const String reportGuide = '/diary/write/report';

  // Records shell + branches.
  static const String records = '/records';
  static const String recordsDiary = '/records/diary';
  static const String recordsReport = '/records/report';
  static const String recordsCounsel = '/records/counsel';

  static const String shortformPlayer = '/player';
  static const String settings = '/settings';
  static const String myPage = '/settings/my-page';
  static const String chatbotSettings = '/settings/chatbot';
  static const String notifications = '/notifications';
}
