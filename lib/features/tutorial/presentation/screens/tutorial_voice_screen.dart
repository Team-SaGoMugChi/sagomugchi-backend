import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/tutorial_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/security_card.dart';
import '../widgets/tutorial_step_scaffold.dart';

/// Screen 13 — 튜토리얼 3/5 음성 입력 연습. Explains STT + voice analysis.
class TutorialVoiceScreen extends StatelessWidget {
  const TutorialVoiceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return TutorialStepScaffold(
      appBarTitle: '튜토리얼 3/5',
      current: 2,
      stepLabel: '음성 입력 연습',
      headline: '말한 내용이 글로 바뀌어요',
      subtitle: 'Oddo는 당신의 목소리를 인식해 대화 내용을 글로 바꾸고,\n목소리의 변화까지 함께 분석해요.',
      primaryLabel: '다음으로',
      onPrimary: () => context.pushNamed(AppRoute.tutorialFace),
      body: const [
        // TODO: 마이크를 들고 있는 포즈로 교체 예정
        MascotSceneCard(
          pose: MascotPose.mic,
          bubble: '편하게 이야기해보세요!\n당신의 이야기를 정확한 기록으로 남겨드릴게요 😊',
        ),
        _FlowCard(),
        _RealtimeCard(),
        SecurityCard(
          title: '안전하고 비밀이 보장돼요',
          description: '모든 대화 내용은 암호화되어 안전하게 보호되며, 당신만을 위한 분석에 사용돼요.',
        ),
      ],
    );
  }
}

/// "이렇게 진행돼요" — 음성 입력 → 음성 분석 → 텍스트 변환.
class _FlowCard extends StatelessWidget {
  const _FlowCard();

  @override
  Widget build(BuildContext context) {
    const steps = TutorialDummy.voiceFlow;
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CardSectionHeader(
              icon: Icons.tune_rounded, title: '이렇게 진행돼요'),
          Gap.h16,
          Row(
            children: [
              for (var i = 0; i < steps.length; i++) ...[
                if (i > 0)
                  const Icon(Icons.arrow_forward_rounded,
                      size: 16, color: AppColors.textTertiary),
                Expanded(
                  child: Column(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: const BoxDecoration(
                          color: AppColors.primarySoft,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(steps[i].icon,
                            size: 20, color: AppColors.primary),
                      ),
                      const SizedBox(height: 6),
                      Text(steps[i].title,
                          textAlign: TextAlign.center,
                          style: AppTypography.caption),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

/// "실시간 변환" — waveform + example converted sentence.
class _RealtimeCard extends StatelessWidget {
  const _RealtimeCard();

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CardSectionHeader(
              icon: Icons.graphic_eq_rounded, title: '실시간 변환'),
          Gap.h12,
          const _Waveform(),
          Gap.h12,
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(
              color: AppColors.backgroundAlt,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: const Row(
              children: [
                Expanded(
                  child: Text(TutorialDummy.exampleSentence,
                      style: AppTypography.bodySecondary),
                ),
                SizedBox(width: 8),
                Icon(Icons.edit_outlined,
                    size: 16, color: AppColors.textTertiary),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Waveform extends StatelessWidget {
  const _Waveform();

  static const List<double> _bars = [
    8, 16, 24, 14, 28, 18, 10, 22, 30, 16, 12, 26, 20, 14, 8, 18
  ];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 32,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          for (final h in _bars)
            Container(
              width: 3,
              height: h,
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
        ],
      ),
    );
  }
}
