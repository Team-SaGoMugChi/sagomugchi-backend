import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/diary_flow_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../widgets/diary_step_header.dart';

/// Screen 41 — Step 3. 영상 제작 로딩. Auto-advances to the finished-video
/// screen after a dummy delay.
class DiaryStep3VideoLoadingScreen extends StatefulWidget {
  const DiaryStep3VideoLoadingScreen({super.key});

  @override
  State<DiaryStep3VideoLoadingScreen> createState() =>
      _DiaryStep3VideoLoadingScreenState();
}

class _DiaryStep3VideoLoadingScreenState
    extends State<DiaryStep3VideoLoadingScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(const Duration(seconds: 3), () {
      if (mounted) context.pushReplacementNamed(AppRoute.diaryStep3VideoDone);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              const DiaryStepHeader(currentStep: 2),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Center(
                        child: Text('Step 3. 영상 제작',
                            style: AppTypography.bodySecondary.copyWith(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w700)),
                      ),
                      Gap.h8,
                      const Text('영상을 만들고 있어요',
                          textAlign: TextAlign.center,
                          style: AppTypography.title),
                      Gap.h8,
                      const Text('모든 내용을 종합해\n오늘의 이야기를 영상으로 제작하고 있어요.',
                          textAlign: TextAlign.center,
                          style: AppTypography.bodySecondary),
                      Gap.h24,
                      // TODO: 카메라/노트북으로 영상을 만드는 포즈로 교체 예정
                      const Center(
                          child: MascotImage(pose: MascotPose.camera, size: 160)),
                      Gap.h24,
                      ClipRRect(
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                        child: const LinearProgressIndicator(
                          value: 0.6,
                          minHeight: 8,
                          backgroundColor: AppColors.primarySoftBorder,
                          valueColor: AlwaysStoppedAnimation(AppColors.primary),
                        ),
                      ),
                      Gap.h8,
                      const Center(
                        child: Text('영상을 정성스럽게 만들고 있어요. 예상 소요시간 1~3분',
                            style: AppTypography.caption),
                      ),
                      Gap.h24,
                      const OddoCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            CardSectionHeader(
                                icon: Icons.auto_awesome_rounded,
                                title: 'AI 일기 요약'),
                            Gap.h8,
                            Text(DiaryFlowDummy.videoMakingSummary,
                                style: AppTypography.body),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
