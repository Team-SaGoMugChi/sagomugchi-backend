import 'package:oddo/features/auth/data/models/app_user.dart';
import 'package:oddo/features/diary/data/models/counsel_session.dart';
import 'package:oddo/features/diary/data/models/diary_entry.dart';
import 'package:oddo/features/diary/data/models/emotion_report.dart';

/// Central in-memory sample data for the prototype. Dummy data sources read
/// from here. When real remote/local data sources land, this file (and the
/// `*DummyDataSource`s) are the only things to drop.
abstract final class DummySeed {
  DummySeed._();

  static const AppUser user = AppUser(
    id: 'u_001',
    email: 'oddo_user@email.com',
    nickname: '오디',
    onboardingDone: true,
  );

  static final DiaryEntry diaryJan14 = DiaryEntry(
    id: 'd_20260114',
    date: DateTime(2026, 1, 14),
    transcript: '오늘 학교에서 친구랑 조금 다퉜어. 괜히 말이 예민하게 나가서 후회돼...',
    summary: '오늘은 친구와의 대화에서 오해가 생겨 속상함과 후회를 느낀 하루였어요.',
    emotionKeywords: ['속상함', '후회', '답답함', '미안함'],
    videoUrl: 'dummy://video/20260114',
    emotionIntensity: 72,
    emotionStability: 48,
    writtenAt: DateTime(2026, 1, 14, 18, 42),
  );

  static final List<DiaryEntry> diaryEntries = [diaryJan14];

  static final EmotionReport reportJan14 = EmotionReport(
    date: DateTime(2026, 1, 14),
    emotionDistribution: {
      '속상함': 0.42,
      '후회': 0.28,
      '답답함': 0.18,
      '평온': 0.12,
    },
    emotionIntensity: 72,
    recoveryPossibility: 64,
    analysisComment:
        '오늘은 관계에서 생긴 오해가 마음에 크게 남은 날이에요. 하지만 상대를 이해하고 싶어 하는 마음도 함께 나타났어요.',
    behaviorGuides: [
      '오늘 느낀 감정을 한 문장으로 다시 적어보기',
      '친구에게 바로 사과하기보다 먼저 내 마음을 정리하기',
      '내일 짧고 차분한 문장으로 대화 시작하기',
    ],
    recommendedActivities: ['가벼운 산책', '따뜻한 차 마시기', '감정 키워드 일기 쓰기'],
  );

  static final CounselSession counselJan14 = CounselSession(
    date: DateTime(2026, 1, 14),
    startedAt: DateTime(2026, 1, 14, 18, 30),
    endedAt: DateTime(2026, 1, 14, 19, 12),
    messages: const [
      CounselMessage(speaker: CounselSpeaker.oddo, text: '안녕하세요! 오늘 하루는 어땠나요?'),
      CounselMessage(
          speaker: CounselSpeaker.user, text: '오늘 학교에서 친구랑 조금 다툼이 있었어.'),
      CounselMessage(
          speaker: CounselSpeaker.oddo,
          text: '속상했겠어요. 어떤 상황에서 그렇게 말이 나가게 된 걸까요?'),
      CounselMessage(
          speaker: CounselSpeaker.user, text: '내가 한 말을 친구가 오해한 것 같았고...'),
    ],
  );
}
