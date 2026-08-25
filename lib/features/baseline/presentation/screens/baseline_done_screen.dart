import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/security_card.dart';
import '../widgets/metric_tile.dart';

/// Screen 21 — Baseline 완료. Shows the emotion-baseline summary + saved-data
/// checklist → 심리테스트.
class BaselineDoneScreen extends StatelessWidget {
  const BaselineDoneScreen({super.key});

  @override
  Widget build(BuildContext context) {
    const metrics = BaselineDummy.metrics;
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // TODO: 체크 표시를 들고 기뻐하는 포즈로 교체 예정 (character_sheet 기반)
                      const Center(
                          child: MascotImage(pose: MascotPose.check, size: 140)),
                      Gap.h16,
                      const Text('첫 측정이 완료됐어요!',
                          textAlign: TextAlign.center,
                          style: AppTypography.display),
                      Gap.h8,
                      const Text('이제 Oddo가 당신의 감정 변화를\n더 잘 이해할 수 있어요.',
                          textAlign: TextAlign.center,
                          style: AppTypography.bodySecondary),
                      Gap.h24,
                      const Text('나의 감정 기준 요약', style: AppTypography.subtitle),
                      Gap.h12,
                      Row(
                        children: [
                          Expanded(child: MetricTile(metric: metrics[0])),
                          Gap.w12,
                          Expanded(child: MetricTile(metric: metrics[1])),
                        ],
                      ),
                      Gap.h12,
                      Row(
                        children: [
                          Expanded(child: MetricTile(metric: metrics[2])),
                          Gap.w12,
                          Expanded(child: MetricTile(metric: metrics[3])),
                        ],
                      ),
                      Gap.h16,
                      OddoCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final line in BaselineDummy.completionSummary)
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 6),
                                child: Row(
                                  children: [
                                    const Icon(Icons.check_circle_rounded,
                                        size: 18, color: AppColors.success),
                                    const SizedBox(width: 8),
                                    Text(line, style: AppTypography.body),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      Gap.h16,
                      const SecurityCard(
                        title: '데이터는 안전하게 보호돼요',
                        description: '감정 기준 데이터는 암호화되어 나만을 위한 분석에만 사용돼요.',
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '심리테스트 시작하기',
                  onPressed: () => context.pushNamed(AppRoute.psychTestList),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
