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
import '../../../../widgets/primary_button.dart';
import '../widgets/diary_step_header.dart';

/// Screen 42 — Step 3. 영상 제작 완료·영상 확인. Player is a dummy placeholder.
class DiaryStep3VideoDoneScreen extends StatefulWidget {
  const DiaryStep3VideoDoneScreen({super.key});

  @override
  State<DiaryStep3VideoDoneScreen> createState() =>
      _DiaryStep3VideoDoneScreenState();
}

class _DiaryStep3VideoDoneScreenState extends State<DiaryStep3VideoDoneScreen> {
  int? _rating;

  static const List<String> _emojis = ['😊', '🙂', '😕'];

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
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.sm,
                    AppSpacing.screenH,
                    AppSpacing.md,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const _CompleteBanner(),
                      Gap.h16,
                      const _VideoPlayerPlaceholder(),
                      Gap.h16,
                      const OddoCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            CardSectionHeader(
                              icon: Icons.subscriptions_outlined,
                              title: '영상 요약',
                            ),
                            Gap.h8,
                            Text(
                              DiaryFlowDummy.videoSummary,
                              style: AppTypography.body,
                            ),
                          ],
                        ),
                      ),
                      Gap.h16,
                      const Text('이 영상은 어땠나요?', style: AppTypography.subtitle),
                      Gap.h12,
                      Row(
                        children: [
                          for (
                            var i = 0;
                            i < DiaryFlowDummy.ratingOptions.length;
                            i++
                          ) ...[
                            if (i > 0) Gap.w12,
                            Expanded(
                              child: _RatingChip(
                                emoji: _emojis[i],
                                label: DiaryFlowDummy.ratingOptions[i],
                                selected: _rating == i,
                                onTap: () => setState(() => _rating = i),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.xs,
                  AppSpacing.screenH,
                  AppSpacing.xs,
                ),
                child: SafeArea(
                  top: false,
                  child: PrimaryButton(
                    label: '다음 단계로',
                    onPressed: () =>
                        context.pushNamed(AppRoute.diaryStep4CounselIntro),
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

class _CompleteBanner extends StatelessWidget {
  const _CompleteBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadius.card,
      ),
      child: Row(
        children: [
          const Icon(
            Icons.check_circle_rounded,
            size: 22,
            color: AppColors.primary,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '영상이 완성되었어요!',
                  style: AppTypography.bodySecondary.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                const Text(
                  'AI가 제작한 영상을 확인해 보세요.',
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
          // TODO: 기뻐하는 작은 포즈로 교체 예정
          const MascotImage(pose: MascotPose.celebrate, size: 44),
        ],
      ),
    );
  }
}

class _VideoPlayerPlaceholder extends StatelessWidget {
  const _VideoPlayerPlaceholder();

  @override
  Widget build(BuildContext context) {
    // The player itself is the replay affordance — tap to open the full-screen
    // shortform player (replaces the former bottom "다시 보기" button).
    return GestureDetector(
      onTap: () => context.pushNamed(AppRoute.shortformPlayer),
      child: ClipRRect(
        borderRadius: AppRadius.card,
        child: AspectRatio(
          aspectRatio: 1,
          child: Stack(
            fit: StackFit.expand,
            children: [
              Container(color: AppColors.callBackground),
              // TODO: 실제 영상 썸네일/플레이어로 교체 예정
              const Center(
                child: MascotImage(
                  pose: MascotPose.front,
                  size: 150,
                  onDark: true,
                ),
              ),
              const Center(
                child: Icon(
                  Icons.play_circle_fill_rounded,
                  size: 56,
                  color: Colors.white,
                ),
              ),
              Positioned(
                left: 12,
                right: 12,
                bottom: 12,
                child: Row(
                  children: [
                    Text(
                      DiaryFlowDummy.videoPosition,
                      style: AppTypography.caption.copyWith(
                        color: AppColors.callTextPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.all(
                          Radius.circular(AppRadius.pill),
                        ),
                        child: LinearProgressIndicator(
                          value: 0.05,
                          minHeight: 4,
                          backgroundColor: Colors.white24,
                          valueColor: AlwaysStoppedAnimation(AppColors.primary),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      DiaryFlowDummy.videoDuration,
                      style: AppTypography.caption.copyWith(
                        color: AppColors.callTextPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Icon(
                      Icons.fullscreen_rounded,
                      size: 18,
                      color: AppColors.callTextPrimary,
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

class _RatingChip extends StatelessWidget {
  const _RatingChip({
    required this.emoji,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String emoji;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: AppRadius.button,
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 22)),
            const SizedBox(height: 4),
            Text(
              label,
              style: AppTypography.caption.copyWith(
                color: selected ? AppColors.primary : AppColors.textSecondary,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
