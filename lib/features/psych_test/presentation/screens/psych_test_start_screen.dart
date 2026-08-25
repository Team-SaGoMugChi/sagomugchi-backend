import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/icon_info_tile.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/step_progress_bar.dart';
import '../../../../widgets/tip_card.dart';

/// Screen 23 — 심리테스트 시작 안내. → Big 5 질문.
class PsychTestStartScreen extends StatelessWidget {
  const PsychTestStartScreen({super.key});

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
                    child: Text('심리테스트 진행 중',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                child: StepProgressBar(
                    labels: PsychTestDummy.journeySteps, currentIndex: 0),
              ),
              const Expanded(
                child: SingleChildScrollView(
                  padding: EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('테스트를 시작해볼까요?',
                                    style: AppTypography.display),
                                Gap.h8,
                                Text(
                                    'Big 5 성격검사, MBTI, 성향 분석을 통해\n당신의 성향과 감정을 파악해요.',
                                    style: AppTypography.bodySecondary),
                              ],
                            ),
                          ),
                          // TODO: 클립보드를 들고 손 흔드는 포즈로 교체 예정
                          MascotImage(pose: MascotPose.clipboard, size: 84),
                        ],
                      ),
                      Gap.h20,
                      OddoCard(child: _GuideList()),
                      Gap.h12,
                      TipCard(tips: ['조용하고 편안한 환경에서 진행하면 더 집중할 수 있어요.']),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '테스트 시작하기',
                  onPressed: () => context.pushNamed(AppRoute.psychTestBig5),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GuideList extends StatelessWidget {
  const _GuideList();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        IconInfoTile(
          icon: Icons.schedule_rounded,
          title: '소요 시간',
          description: '총 약 20~30분 정도 소요돼요. 중간에 나가도 이어서 진행할 수 있어요.',
        ),
        Divider(color: AppColors.divider, height: 1),
        IconInfoTile(
          icon: Icons.check_circle_outline_rounded,
          title: '정답은 없어요',
          description: '좋고 나쁜 답은 없어요. 지금의 나와 가장 가까운 답을 선택해주세요.',
        ),
        Divider(color: AppColors.divider, height: 1),
        IconInfoTile(
          icon: Icons.lock_outline_rounded,
          title: '안전하게 보호돼요',
          description: '모든 응답은 안전하게 보호되며, 당신만의 맞춤 분석에 사용돼요.',
        ),
        Divider(color: AppColors.divider, height: 1),
        IconInfoTile(
          icon: Icons.pause_circle_outline_rounded,
          title: '잠시 나가도 괜찮아요',
          description: '부담 갖지 말고 천천히, 편한 속도로 진행해주세요.',
        ),
        Divider(color: AppColors.divider, height: 1),
        IconInfoTile(
          icon: Icons.chat_bubble_outline_rounded,
          title: '제가 옆에서 도와줄게요!',
          description: '어려우면 언제든 Oddo에게 물어보세요.',
        ),
      ],
    );
  }
}
