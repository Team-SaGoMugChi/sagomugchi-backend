import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/security_note.dart';
import '../../../../widgets/step_indicator.dart';
import '../../../../widgets/tip_card.dart';

/// Screen 36 — Step 1. 말하기 안내. → 실시간 말하기.
class DiaryStep1IntroScreen extends StatelessWidget {
  const DiaryStep1IntroScreen({super.key});

  static const List<String> _steps = ['말하기', '확인하기', '영상 제작', '상담하기'];

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
                    child: Text('일기 작성하기',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  IconButton(
                    icon: const Icon(Icons.help_outline_rounded, size: 20),
                    onPressed: () => showHelpSheet(
                      context,
                      title: '일기 작성 도움말',
                      items: const [
                        '말하기 → 확인하기 → 영상 제작 → 상담하기 4단계로 진행돼요.',
                        '말하기는 영상통화처럼 편하게 이야기하면 돼요.',
                        '완료하면 이 날짜의 일기·리포트·상담 기록이 저장돼요.',
                      ],
                    ),
                  ),
                ],
              ),
              const Padding(
                padding: EdgeInsets.symmetric(
                    horizontal: AppSpacing.screenH, vertical: AppSpacing.sm),
                child: StepIndicator(steps: _steps, currentIndex: 0),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.xl),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text('Step 1. 말하기',
                          style: AppTypography.bodySecondary.copyWith(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w700)),
                      Gap.h4,
                      const Text('AI와 대화하며 오늘을 기록해요',
                          style: AppTypography.title),
                      Gap.h8,
                      const Text('편하게 이야기하면 AI가 실시간으로\n당신의 감정을 분석하고 기록해줄 거예요.',
                          style: AppTypography.bodySecondary),
                      Gap.h16,
                      const _SceneCard(),
                      Gap.h16,
                      const Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        alignment: WrapAlignment.center,
                        children: [
                          _FeatureChip(
                              icon: Icons.chat_bubble_outline_rounded,
                              label: 'AI 실시간 대화'),
                          _FeatureChip(
                              icon: Icons.insights_rounded, label: '감정 실시간 분석'),
                          _FeatureChip(
                              icon: Icons.lock_outline_rounded,
                              label: '안전한 비밀보장'),
                        ],
                      ),
                      Gap.h20,
                      PrimaryButton(
                        label: '말하기 시작하기',
                        leadingIcon: Icons.videocam_rounded,
                        onPressed: () =>
                            context.pushNamed(AppRoute.diaryStep1Live),
                      ),
                      Gap.h16,
                      const TipCard(tips: [
                        '편한 장소에서 이야기해보세요.',
                        '어떤 이야기든 좋아요. 있는 그대로 말해주세요.',
                        '중간에 멈춰도 괜찮아요.',
                      ]),
                      Gap.h12,
                      const SecurityNote(text: '모든 대화 내용은 안전하게 보호돼요.'),
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

/// Wide illustration card: the mascot in a room, waving.
class _SceneCard extends StatelessWidget {
  const _SceneCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 180,
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadius.card,
      ),
      alignment: Alignment.center,
      // TODO: 방 안 배경 + 중앙에서 손 흔드는 포즈로 교체 예정
      child: const MascotImage(pose: MascotPose.waving, size: 140),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  const _FeatureChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppColors.primary),
          const SizedBox(width: 5),
          Text(label, style: AppTypography.caption),
        ],
      ),
    );
  }
}
