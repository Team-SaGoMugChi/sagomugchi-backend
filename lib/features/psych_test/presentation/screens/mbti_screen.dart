import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../widgets/psych_question_screen.dart';

/// Screen 25 — MBTI 성격유형 검사 질문 (two illustrated choices). → 성향 분석.
class MbtiScreen extends StatelessWidget {
  const MbtiScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return PsychQuestionScreen(
      testTitle: 'MBTI 성격유형 검사',
      journeyIndex: 2,
      questionNumber: 7,
      totalQuestions: 60,
      question: PsychTestDummy.mbtiSample,
      layout: PsychOptionLayout.duo,
      hint: '상황이 모두 달라도 내가 편안하게 느끼는 쪽을 기준으로 선택해 주세요.',
      // TODO: 책을 보며 생각하는 포즈로 교체 예정
      mascotPose: MascotPose.front,
      onNext: () => context.pushNamed(AppRoute.psychTestTendency),
    );
  }
}
