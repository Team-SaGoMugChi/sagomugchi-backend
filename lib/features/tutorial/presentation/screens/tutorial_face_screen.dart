import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/tutorial_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/tip_card.dart';
import '../widgets/tutorial_step_scaffold.dart';

/// Screen 14 — 튜토리얼 4/5 표정 입력 연습. Explains facial baseline.
class TutorialFaceScreen extends StatelessWidget {
  const TutorialFaceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return TutorialStepScaffold(
      appBarTitle: '튜토리얼 4/5',
      current: 3,
      stepLabel: '표정 입력 연습',
      headline: '표정 변화도 함께 살펴봐요',
      subtitle: 'Oddo는 카메라를 통해 표정 변화를 감지해요.\n편안하고 자연스러운 표정을 보여주세요!',
      primaryLabel: '다음으로',
      onPrimary: () => context.pushNamed(AppRoute.tutorialMethod),
      body: const [
        // TODO: 작은 거울을 들고 있는 포즈로 교체 예정
        MascotSceneCard(
          pose: MascotPose.mirror,
          bubble: '다양한 표정은\n감정 분석에 도움이 돼요! 😀 😐 😢',
        ),
        _FaceStepsCard(),
        _FaceChecklistCard(),
        TipCard(tips: TutorialDummy.faceTips),
      ],
    );
  }
}

class _FaceStepsCard extends StatelessWidget {
  const _FaceStepsCard();

  @override
  Widget build(BuildContext context) {
    const steps = TutorialDummy.faceSteps;
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CardSectionHeader(
              icon: Icons.camera_alt_outlined, title: '연습 방법'),
          Gap.h16,
          Row(
            children: [
              for (var i = 0; i < steps.length; i++) ...[
                if (i > 0)
                  const Icon(Icons.arrow_forward_rounded,
                      size: 16, color: AppColors.textTertiary),
                Expanded(
                  child: Column(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: const BoxDecoration(
                          color: AppColors.primarySoft,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(steps[i].icon,
                            size: 20, color: AppColors.primary),
                      ),
                      const SizedBox(height: 6),
                      Text('${i + 1}. ${steps[i].title}',
                          textAlign: TextAlign.center,
                          style: AppTypography.caption),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _FaceChecklistCard extends StatelessWidget {
  const _FaceChecklistCard();

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CardSectionHeader(
              icon: Icons.check_circle_outline_rounded, title: '촬영 확인해주세요'),
          Gap.h12,
          for (final item in TutorialDummy.faceChecklist)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_rounded,
                      size: 18, color: AppColors.primary),
                  const SizedBox(width: 8),
                  Expanded(child: Text(item, style: AppTypography.body)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
