import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/info_callout.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/progress_dots.dart';

/// Screen 29 — 챗봇 페르소나 설정 인트로. → 상세 설정.
class PersonaIntroScreen extends StatelessWidget {
  const PersonaIntroScreen({super.key});

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
                    child: Text('페르소나 설정',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              const ProgressDots(count: 3, current: 0),
              const Expanded(
                child: SingleChildScrollView(
                  padding: EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text('어떤 챗봇과 함께하고 싶나요?\n챗봇 페르소나를 설정해볼게요',
                          style: AppTypography.display),
                      Gap.h8,
                      Text('당신에게 가장 잘 맞는 챗봇을 만들기 위해\n외모, 말투, 성격을 선택해주세요.',
                          style: AppTypography.bodySecondary),
                      Gap.h20,
                      // TODO: 윙크하며 손 흔드는 포즈로 교체 예정
                      MascotSceneCard(
                        pose: MascotPose.wink,
                        bubble: '내가 당신의 좋은 친구가 되어줄게요!\n함께 만들어봐요 😊',
                      ),
                      Gap.h16,
                      InfoCallout(
                        icon: Icons.psychology_outlined,
                        title: '페르소나란?',
                        description: '챗봇의 외모, 말투, 성격을 설정하면 당신에게 더 잘 맞는 대화를 할 수 있어요.',
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '설정 시작하기',
                  onPressed: () => context.pushNamed(AppRoute.personaDetail),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
