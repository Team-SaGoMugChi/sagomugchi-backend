import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/progress_dots.dart';
import '../../../../widgets/security_card.dart';

/// Screen 22 — 심리테스트 안내·검사 목록 (Big5 / MBTI / 성향 분석).
class PsychTestListScreen extends StatelessWidget {
  const PsychTestListScreen({super.key});

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
                    child: Text('심리테스트',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              const ProgressDots(count: 3, current: 0),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text.rich(
                                  TextSpan(children: [
                                    TextSpan(text: '진행할 '),
                                    TextSpan(
                                        text: '테스트',
                                        style:
                                            TextStyle(color: AppColors.primary)),
                                    TextSpan(text: '를\n안내해요'),
                                  ]),
                                  style: AppTypography.display,
                                ),
                                Gap.h8,
                                Text('총 3가지 테스트를 진행해요.',
                                    style: AppTypography.bodySecondary),
                              ],
                            ),
                          ),
                          // TODO: 클립보드를 들고 안내하는 포즈로 교체 예정
                          MascotImage(pose: MascotPose.clipboard, size: 88),
                        ],
                      ),
                      Gap.h20,
                      for (var i = 0; i < PsychTestDummy.testList.length; i++) ...[
                        if (i > 0) Gap.h12,
                        _TestCard(
                            index: i + 1, info: PsychTestDummy.testList[i]),
                      ],
                      Gap.h16,
                      const SecurityCard(
                        title: '결과는 안전하게 보호돼요',
                        description: '모든 결과는 안전하게 보호되며, 맞춤 서비스에만 사용돼요.',
                      ),
                      Gap.h8,
                      Center(
                        child: TextButton(
                          onPressed: () =>
                              context.pushNamed(AppRoute.psychTestResume),
                          child: const Text('이전에 진행하던 테스트 이어하기'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '테스트 시작하기',
                  onPressed: () => context.pushNamed(AppRoute.psychTestStart),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TestCard extends StatelessWidget {
  const _TestCard({required this.index, required this.info});

  final int index;
  final PsychTestInfo info;

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: const BoxDecoration(
                    color: AppColors.primarySoft, shape: BoxShape.circle),
                child: Icon(info.icon, size: 20, color: AppColors.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text('$index. ${info.title}',
                    style: AppTypography.body
                        .copyWith(fontWeight: FontWeight.w700)),
              ),
              _DurationChip(info.duration),
            ],
          ),
          Gap.h12,
          Text(info.description, style: AppTypography.bodySecondary),
          Gap.h12,
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final tag in info.tags) _Tag(tag),
            ],
          ),
        ],
      ),
    );
  }
}

class _DurationChip extends StatelessWidget {
  const _DurationChip(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.schedule_rounded, size: 13, color: AppColors.primary),
        const SizedBox(width: 3),
        Text(label,
            style: AppTypography.caption.copyWith(
                color: AppColors.primary, fontWeight: FontWeight.w600)),
      ],
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.backgroundAlt,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(label, style: AppTypography.caption),
    );
  }
}
