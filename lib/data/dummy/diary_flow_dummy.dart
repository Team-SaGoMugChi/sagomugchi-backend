import '../../features/diary/data/models/counsel_session.dart';

/// Dummy content for the daily diary-write flow (Step 2–4 + report) beyond the
/// core entry/report already in [DummySeed]. Replace with real generated
/// content later.
abstract final class DiaryFlowDummy {
  DiaryFlowDummy._();

  /// 40 — Step 2 follow-up question chat (Oddo ↔ user turns).
  static const List<CounselMessage> step2Chat = [
    CounselMessage(
      speaker: CounselSpeaker.oddo,
      text: '더 멋진 일기를 만들기 위해 몇 가지 더 여쭤볼게요!\n편하게 답해주세요 :)',
    ),
    CounselMessage(
      speaker: CounselSpeaker.oddo,
      text: '친구와의 대화에서 가장 속상했던 순간은 언제였나요?',
    ),
    CounselMessage(
      speaker: CounselSpeaker.user,
      text: '내 마음을 이해해주지 않고 바로 반박했을 때 속상했어.',
    ),
    CounselMessage(speaker: CounselSpeaker.oddo, text: '그때 기분은 어땠나요?'),
    CounselMessage(
      speaker: CounselSpeaker.user,
      text: '정말 서운하고, 스트레스도 확 풀렸어.',
    ),
    CounselMessage(
      speaker: CounselSpeaker.oddo,
      text: '그 장면을 영상에서 어떻게 표현하면 좋을까요?\n(예: 밝은 분위기, 잔잔한 음악, 차분한 색감)',
    ),
  ];

  /// 41 — AI diary summary shown while the video is being made.
  static const String videoMakingSummary =
      '친구와의 오해로 속상했지만, 마음을 돌아보며 내 감정을 이해하려고 노력한 하루였어요.';

  /// 42 — finished video summary + dummy playback times.
  static const String videoSummary =
      '오늘은 친구와의 일로 서운하고 화가 났지만, 이후에는 나의 감정을 돌아보고 오해를 풀고 싶다는 생각을 했어요.';
  static const String videoPosition = '00:03';
  static const String videoDuration = '01:32';

  /// 42 — video rating options.
  static const List<String> ratingOptions = ['좋았어요', '보통이에요', '별로였어요'];

  /// 44 — counselor's opening line + live status.
  static const String counselBubble =
      '천천히 이야기해도 괜찮아요.\n오늘 가장 마음에 남는 순간을 함께 돌아봐요.';
  static const String counselStatus = '탄카츄와 영상 상담 중';
  static const String counselTimer = '00:08:12';
}
