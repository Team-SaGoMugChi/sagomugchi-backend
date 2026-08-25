import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../widgets/psych_question_screen.dart';

/// Screen 24 — Big 5 질문 진행 (5-point Likert). → MBTI.
class Big5Screen extends StatelessWidget {
  const Big5Screen({super.key});

  @override
  Widget build(BuildContext context) {
    return PsychQuestionScreen(
      testTitle: 'Big 5 성격검사',
      journeyIndex: 1,
      questionNumber: 12,
      totalQuestions: 50,
      question: PsychTestDummy.big5Sample,
      layout: PsychOptionLayout.likert,
      hint: '솔직하게 답변해주세요. 정답은 없어요, 당신을 더 잘 이해하기 위한 질문이에요.',
      // TODO: 손 흔들며 응원하는 포즈로 교체 예정
      mascotPose: MascotPose.waving,
      onNext: () => context.pushNamed(AppRoute.psychTestMbti),
    );
  }
}
