import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/tutorial_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/speech_bubble.dart';
import '../../../../widgets/tip_card.dart';
import '../widgets/tutorial_step_scaffold.dart';

/// Screen 10 — 튜토리얼 1/5 안내. "베이스라인 측정 시작하기" with an in-card
/// video-call preview. → 통화 연습.
class TutorialIntroScreen extends StatelessWidget {
  const TutorialIntroScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return TutorialStepScaffold(
      appBarTitle: '튜토리얼 1/5',
      current: 0,
      stepLabel: '베이스라인 측정 시작하기',
      stepLabelIcon: Icons.videocam_rounded,
      leadingClose: true,
      showHelp: false,
      headline: '안녕하세요! 저는 Oddo예요',
      subtitle: '앞으로 영상 통화를 통해 당신의 감정을 이해하고,\n더 나은 하루를 함께 만들어 가요.',
      primaryLabel: '네, 시작할게요!',
      primaryIcon: Icons.videocam_rounded,
      onPrimary: () => context.pushNamed(AppRoute.tutorialCall),
      body: const [
        _VideoPreviewCard(),
        _BaselineInfoCard(),
        TipCard(tips: TutorialDummy.introTips),
      ],
    );
  }
}

/// In-card video-call mock: REC chip, the mascot with an "Oddo" label, a
/// speech bubble, and call controls.
class _VideoPreviewCard extends StatelessWidget {
  const _VideoPreviewCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.card,
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          const Row(
            children: [
              _RecChip(),
              Spacer(),
              Icon(Icons.volume_up_rounded,
                  size: 18, color: AppColors.textTertiary),
            ],
          ),
          Gap.h8,
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Column(
                children: [
                  // TODO: 영상통화 안에서 손 흔드는 포즈로 교체 예정
                  const MascotImage(pose: MascotPose.waving, size: 96),
                  Gap.h4,
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Text('Oddo',
                        style: AppTypography.caption.copyWith(
                            color: AppColors.textOnPrimary,
                            fontWeight: FontWeight.w700)),
                  ),
                ],
              ),
              Gap.w12,
              const Expanded(
                child: SpeechBubble(
                    text: '우리가 처음 만나는 시간이네요.\n준비가 되셨다면 시작해볼까요? 😊'),
              ),
            ],
          ),
          Gap.h16,
          const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _ControlButton(icon: Icons.mic_rounded),
              SizedBox(width: 16),
              _ControlButton(icon: Icons.videocam_rounded),
              SizedBox(width: 16),
              _ControlButton(icon: Icons.call_end_rounded, danger: true),
              SizedBox(width: 16),
              _ControlButton(icon: Icons.volume_up_rounded),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecChip extends StatelessWidget {
  const _RecChip();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.backgroundAlt,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration:
                const BoxDecoration(color: AppColors.error, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text('REC',
              style: AppTypography.caption.copyWith(
                  color: AppColors.textSecondary, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

class _ControlButton extends StatelessWidget {
  const _ControlButton({required this.icon, this.danger = false});

  final IconData icon;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: danger ? AppColors.error : AppColors.backgroundAlt,
        shape: BoxShape.circle,
      ),
      child: Icon(icon,
          size: 20,
          color: danger ? AppColors.textOnPrimary : AppColors.textSecondary),
    );
  }
}

/// "베이스라인이란?" explainer callout.
class _BaselineInfoCard extends StatelessWidget {
  const _BaselineInfoCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadius.card,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.verified_user_rounded,
              size: 20, color: AppColors.primary),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('베이스라인이란?',
                    style: AppTypography.bodySecondary
                        .copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                const Text('지금의 감정과 상태를 파악하기 위한 기본 측정이에요. 약 5~7분 정도 소요돼요.',
                    style: AppTypography.caption),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
