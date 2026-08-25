import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';

/// Screen 27 — 심리테스트 중간 저장·이어하기. (Follows the doc spec; the 27
/// mockup file duplicates the 성향 분석 screen.) → 이어서 하기 / 처음부터.
class PsychTestResumeScreen extends StatelessWidget {
  const PsychTestResumeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
                    onPressed: () {
                      if (context.canPop()) context.pop();
                    },
                  ),
                  const Expanded(
                    child: Text('이어서 진행하기',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              const Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    padding: EdgeInsets.symmetric(
                        horizontal: AppSpacing.screenH),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // TODO: 책갈피를 들고 있는 포즈로 교체 예정
                        Center(
                            child: MascotImage(pose: MascotPose.front, size: 140)),
                        Gap.h16,
                        Text('이어서 진행할 수 있어요',
                            textAlign: TextAlign.center,
                            style: AppTypography.display),
                        Gap.h8,
                        Text('지난번에 Q18까지 답했어요.',
                            textAlign: TextAlign.center,
                            style: AppTypography.bodySecondary),
                        Gap.h24,
                        OddoCard(
                          child: Column(
                            children: [
                              _ProgressRow(
                                  title: 'Big 5 성격검사',
                                  status: '완료',
                                  color: AppColors.success),
                              Divider(color: AppColors.divider, height: 20),
                              _ProgressRow(
                                  title: 'MBTI 성격유형 검사',
                                  status: '18 / 60 진행 중',
                                  color: AppColors.primary),
                              Divider(color: AppColors.divider, height: 20),
                              _ProgressRow(
                                  title: '성향 분석',
                                  status: '대기 중',
                                  color: AppColors.textTertiary),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: Column(
                  children: [
                    PrimaryButton(
                      label: '이어서 하기',
                      onPressed: () =>
                          context.pushNamed(AppRoute.psychTestMbti),
                    ),
                    TextButton(
                      onPressed: () =>
                          context.pushNamed(AppRoute.psychTestBig5),
                      child: const Text('처음부터 다시 하기'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProgressRow extends StatelessWidget {
  const _ProgressRow(
      {required this.title, required this.status, required this.color});
  final String title;
  final String status;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(title, style: AppTypography.body)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppRadius.pill),
          ),
          child: Text(status,
              style: AppTypography.caption
                  .copyWith(color: color, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}
