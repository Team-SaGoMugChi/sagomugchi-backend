import 'package:flutter/material.dart';

/// A test summary card on the psych-test list screen (22).
class PsychTestInfo {
  const PsychTestInfo({
    required this.icon,
    required this.title,
    required this.description,
    required this.tags,
    required this.duration,
    required this.questionCount,
  });

  final IconData icon;
  final String title;
  final String description;
  final List<String> tags;
  final String duration;
  final int questionCount;
}

/// One answer option. [illustration] is an optional placeholder icon shown for
/// the illustrated layouts (MBTI / 성향). Real artwork can replace it later.
class PsychOption {
  const PsychOption(this.text, [this.illustration]);
  final String text;
  final IconData? illustration;
}

/// A single test question with its options.
class PsychQuestion {
  const PsychQuestion(this.text, this.options);
  final String text;
  final List<PsychOption> options;
}

/// Static dummy content for the psych-test flow. Mirrors the mockups and
/// `_docs/02`. Real question banks would be loaded per test later — the
/// question screens already read everything from here.
abstract final class PsychTestDummy {
  PsychTestDummy._();

  /// Overall journey steps for the top progress bar.
  static const List<String> journeySteps = ['안내', 'Big 5', 'MBTI', '성향', '완료'];

  // 22 — test list.
  static const List<PsychTestInfo> testList = [
    PsychTestInfo(
      icon: Icons.psychology_outlined,
      title: 'Big 5 성격검사',
      description: '성격의 5가지 주요 요인을 측정해요.',
      tags: ['개방성', '성실성', '외향성', '우호성', '신경성'],
      duration: '약 10분',
      questionCount: 50,
    ),
    PsychTestInfo(
      icon: Icons.extension_outlined,
      title: 'MBTI 성격유형 검사',
      description: '선호 경향을 통해 성격 유형을 파악해요.',
      tags: ['에너지 방향', '인식', '판단', '생활 양식'],
      duration: '약 10분',
      questionCount: 60,
    ),
    PsychTestInfo(
      icon: Icons.favorite_outline_rounded,
      title: '성향 분석',
      description: '가치관, 상황 반응, 행동 성향을 분석해요.',
      tags: ['가치관', '상황 반응', '행동 성향', '대인 관계'],
      duration: '약 5~10분',
      questionCount: 20,
    ),
  ];

  // 24 — Big 5 (5-point Likert).
  static const PsychQuestion big5Sample = PsychQuestion(
    '새로운 사람을 만나는 것이 편한 편인가요?',
    [
      PsychOption('매우 그렇다'),
      PsychOption('그렇다'),
      PsychOption('보통이다'),
      PsychOption('그렇지 않다'),
      PsychOption('전혀 그렇지 않다'),
    ],
  );

  // 25 — MBTI (two illustrated choices).
  static const PsychQuestion mbtiSample = PsychQuestion(
    '에너지를 얻는 방식은\n어느 쪽에 더 가까운가요?',
    [
      PsychOption('사람들과 함께 있을 때\n에너지를 얻는다', Icons.groups_rounded),
      PsychOption('혼자만의 시간을 가질 때\n에너지를 얻는다', Icons.menu_book_rounded),
    ],
  );

  // 26 — 성향 분석 (illustrated list). (Mockup content; the 27 file in
  // _screens duplicates this screen, so 27 follows the doc spec instead.)
  static const PsychQuestion tendencySample = PsychQuestion(
    '스트레스를 받은 상황에서\n나는 보통 어떻게 행동하나요?',
    [
      PsychOption('혼자 조용히 생각하며 마음을 정리한다', Icons.self_improvement_rounded),
      PsychOption('가까운 사람에게 이야기하며 도움을 받는다', Icons.forum_rounded),
      PsychOption('좋아하는 활동에 몰입하며 기분을 전환한다', Icons.palette_outlined),
      PsychOption('운동이나 신체 활동으로 스트레스를 푼다', Icons.directions_run_rounded),
      PsychOption('시간이 지나기를 차분히 기다린다', Icons.schedule_rounded),
    ],
  );
}
