import 'package:flutter/material.dart';

import '../../core/utils/date_formatter.dart';
import '../../theme/app_colors.dart';

/// A summary metric tile on the emotion-report screen (49).
class RecordMetric {
  const RecordMetric(this.icon, this.label, this.value, this.color);
  final IconData icon;
  final String label;
  final String value;
  final Color color;
}

/// Dummy content for the record-viewing screens (홈 작성일 / 일기 상세 /
/// 감정 리포트 / 상담 기록). Reuses [DummySeed] where possible; this adds the
/// extra copy those screens need. Replace with real data later.
abstract final class RecordsDummy {
  RecordsDummy._();

  // 47 — written-day home card.
  static const String homeWrittenTitle = '오늘의 일기가 기록되어 있어요.';

  // 48 — diary detail (date labels follow the viewed date).
  static String diaryDateLabel(DateTime d) => DateFormatter.monthDay(d);
  static String diaryWrittenAt(DateTime d) =>
      '${DateFormatter.fullKoreanDate(d)} · 18:42 작성';
  static const String diaryMood = '평온';
  static const String diaryBody =
      '오늘은 정말 오랜만에 마음이 가벼운 하루였다.\n'
      '아침에 일어나자마자 햇살이 창문으로 스며들어 방 안이 따뜻해졌고, '
      '괜히 기분이 좋아져서 평소보다 천천히 아침을 준비했다.\n\n'
      '점심에는 예전부터 가고 싶던 카페에 들러 따뜻한 라떼를 마셨다. '
      '창밖을 멍하니 바라보고 있으니, 복잡했던 생각들이 조금씩 정리되는 기분이었다.\n\n'
      '오후에는 친구와 짧게 통화를 했는데, 별것 아닌 이야기에도 한참을 웃었다. '
      '누군가와 마음을 나눈다는 게 이렇게 큰 힘이 되는 일이구나 싶었다.\n\n'
      '돌아보면 특별할 것 없는 하루였지만, 그래서 더 소중하게 느껴졌다. '
      '내일도 오늘처럼 마음이 편안한 하루였으면 좋겠다.';

  // 49 — emotion report (period view).
  static String reportTitle(DateTime d) => '${DateFormatter.monthDay(d)} 감정 리포트';
  static String reportPeriod(DateTime d) => '${d.year}년 ${d.month}월 ${d.day}일';
  static const String reportRepEmotion = '평온';
  static const int reportRepPercent = 46;

  static const List<RecordMetric> reportMetrics = [
    RecordMetric(Icons.sentiment_satisfied_alt_rounded, '긍정 감정', '62%',
        Color(0xFF15C47E)),
    RecordMetric(Icons.sentiment_dissatisfied_rounded, '부정 감정', '18%',
        Color(0xFFF04452)),
    RecordMetric(Icons.bolt_rounded, '스트레스 지수', '보통', Color(0xFFFFB020)),
    RecordMetric(Icons.directions_walk_rounded, '활동 기록', '5회',
        AppColors.primary),
  ];

  static const String reportComment =
      '이번 주에는 전반적으로 평온한 감정이 가장 많이 나타났어요. '
      '특히 10일과 14일에는 긍정적인 감정이 크게 증가했어요.';
  static const List<String> reportActivities = ['가벼운 산책', '좋아하는 책 읽기', '따뜻한 식사'];
  static const List<String> reportRecommendations = [
    '규칙적인 수면 패턴 유지',
    '하루 10분 명상',
    '감정을 글로 표현하기',
  ];

  /// 49 — weekly emotion trend points (0..1), for the mini line chart.
  static const List<double> reportTrend = [0.4, 0.55, 0.45, 0.7, 0.5, 0.6, 0.8];

  // 50 — counsel record.
  static String counselTitle(DateTime d) => '${DateFormatter.monthDay(d)} 상담 기록';
  static const String counselTime = '18:30 - 19:12';
  static const String counselSessionLabel = '영상 상담';
}
