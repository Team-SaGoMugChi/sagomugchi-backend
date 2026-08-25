import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../widgets/psych_question_screen.dart';

/// Screen 26 — 성향 분석 질문 진행 (illustrated list). → 심리테스트 완료.
class TendencyScreen extends StatelessWidget {
  const TendencyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return PsychQuestionScreen(
      testTitle: '성향 분석',
      journeyIndex: 3,
      questionNumber: 4,
      totalQuestions: 20,
      question: PsychTestDummy.tendencySample,
      layout: PsychOptionLayout.illustrated,
      hint: '특별한 상황이 떠오르지 않으면 일반적인 경우를 떠올리며 선택해 주세요.',
      // TODO: 곰곰이 생각하는 포즈로 교체 예정
      mascotPose: MascotPose.thinking,
      onNext: () => context.pushNamed(AppRoute.psychTestDone),
    );
  }
}
