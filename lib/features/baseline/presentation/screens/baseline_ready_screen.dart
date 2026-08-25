import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/icon_info_tile.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/security_card.dart';
import '../widgets/baseline_header.dart';

/// Screen 18 — Baseline 준비 체크. Environment checklist → 측정 중.
class BaselineReadyScreen extends StatelessWidget {
  const BaselineReadyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: BaselineHeader(
                  title: '베이스라인 측정 1/2',
                  stepLabels: ['안내 진행', '측정 진행'],
                  activeStep: 1,
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text('측정 준비를 확인할게요',
                          style: AppTypography.display),
                      Gap.h8,
                      const Text('정확한 데이터를 위해 아래 항목을 확인해주세요.',
                          style: AppTypography.bodySecondary),
                      Gap.h16,
                      // TODO: 카메라를 점검하는 포즈로 교체 예정 (character_sheet 기반 점검)
                      const MascotSceneCard(
                        pose: MascotPose.camera,
                        bubble: '최상의 환경에서 측정하면\n더 정확한 결과를 얻을 수 있어요!',
                      ),
                      Gap.h20,
                      OddoCard(
                        child: Column(
                          children: [
                            for (var i = 0;
                                i < BaselineDummy.checklist.length;
                                i++) ...[
                              if (i > 0)
                                const Divider(
                                    color: AppColors.divider, height: 1),
                              IconInfoTile(
                                icon: BaselineDummy.checklist[i].icon,
                                title: BaselineDummy.checklist[i].title,
                                description:
                                    BaselineDummy.checklist[i].description,
                                trailing: const Icon(Icons.check_circle_rounded,
                                    color: AppColors.primary, size: 22),
                              ),
                            ],
                          ],
                        ),
                      ),
                      Gap.h16,
                      const SecurityCard(),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '준비됐어요, 측정 시작하기',
                  leadingIcon: Icons.videocam_rounded,
                  onPressed: () =>
                      context.pushNamed(AppRoute.baselineMeasuring),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
