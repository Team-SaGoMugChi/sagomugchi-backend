import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/persona_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';

/// Screen 31 — 페르소나 설정 완료. → 온보딩 완료.
class PersonaDoneScreen extends StatelessWidget {
  const PersonaDoneScreen({super.key});

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
                    child: Text('설정 완료',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.screenH),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // TODO: 하트를 들고 있는 포즈로 교체 예정
                        const Center(
                            child: MascotImage(pose: MascotPose.heart, size: 140)),
                        Gap.h16,
                        const Text('${PersonaDummy.defaultName}가 준비됐어요!',
                            textAlign: TextAlign.center,
                            style: AppTypography.display),
                        Gap.h8,
                        const Text('앞으로 당신의 하루를 따뜻하게 들어줄게요.',
                            textAlign: TextAlign.center,
                            style: AppTypography.bodySecondary),
                        Gap.h24,
                        OddoCard(
                          child: Column(
                            children: [
                              const _SummaryRow(
                                  label: '이름', value: PersonaDummy.defaultName),
                              const Divider(
                                  color: AppColors.divider, height: 20),
                              const _SummaryRow(
                                  label: '말투', value: PersonaDummy.defaultTone),
                              const Divider(
                                  color: AppColors.divider, height: 20),
                              _SummaryRow(
                                  label: '성격',
                                  value:
                                      PersonaDummy.defaultTraits.join(', ')),
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
                child: PrimaryButton(
                  label: '다음으로',
                  onPressed: () => context.pushNamed(AppRoute.onboardingDone),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 56,
          child: Text(label, style: AppTypography.bodySecondary),
        ),
        Expanded(
          child: Text(value,
              style: AppTypography.body.copyWith(fontWeight: FontWeight.w600)),
        ),
      ],
    );
  }
}
