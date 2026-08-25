import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/tutorial_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/security_note.dart';
import '../widgets/tutorial_header.dart';

/// Screen 16 — 튜토리얼 완료. Celebratory summary → 얼굴·음성 Baseline 안내.
class TutorialDoneScreen extends StatelessWidget {
  const TutorialDoneScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: TutorialHeader(
                  title: '튜토리얼 완료',
                  current: 4,
                  stepLabel: '5/5 단계 완료',
                  showHelp: false,
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // TODO: 두 손을 들고 기뻐하는 포즈로 교체 예정
                      const Center(
                          child: MascotImage(
                              pose: MascotPose.celebrate, size: 150)),
                      Gap.h16,
                      const Text('튜토리얼을 모두 마쳤어요!',
                          textAlign: TextAlign.center,
                          style: AppTypography.display),
                      Gap.h8,
                      const Text(
                        'Oddo와 함께 감정을 이해하고, 더 나은 하루를 만들 준비가 됐어요.\n'
                        '이제 첫 측정을 시작해볼까요?',
                        textAlign: TextAlign.center,
                        style: AppTypography.bodySecondary,
                      ),
                      Gap.h24,
                      OddoCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const CardSectionHeader(
                                icon: Icons.task_alt_rounded, title: '완료한 내용'),
                            Gap.h8,
                            for (final item in TutorialDummy.completionItems)
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 7),
                                child: Row(
                                  children: [
                                    const Icon(Icons.check_circle_rounded,
                                        size: 18, color: AppColors.primary),
                                    const SizedBox(width: 10),
                                    Expanded(
                                        child: Text(item.title,
                                            style: AppTypography.body)),
                                    Icon(item.icon,
                                        size: 16,
                                        color: AppColors.textTertiary),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      Gap.h16,
                      const SecurityNote(
                        text: '측정 데이터는 안전하게 보호되며, 나만을 위한 분석에 사용돼요.',
                        center: true,
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '첫 측정 시작하기',
                  leadingIcon: Icons.videocam_rounded,
                  onPressed: () => context.pushNamed(AppRoute.baselineIntro),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
