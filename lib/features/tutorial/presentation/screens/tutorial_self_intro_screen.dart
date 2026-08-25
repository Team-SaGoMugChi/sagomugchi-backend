import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/tutorial_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/icon_info_tile.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/oddo_card.dart';
import '../widgets/tutorial_step_scaffold.dart';

/// Screen 12 — 튜토리얼 2/5 자기소개 기반 연습.
class TutorialSelfIntroScreen extends StatelessWidget {
  const TutorialSelfIntroScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return TutorialStepScaffold(
      appBarTitle: '튜토리얼 2/5',
      current: 1,
      stepLabel: '자기소개 기반 연습',
      headline: '가볍게 나를 소개해볼까요?',
      subtitle: 'Oddo와 편하게 대화하며 당신에 대해 조금씩 알아갈 거예요.\n부담 없이 이야기해보세요.',
      primaryLabel: '연습 시작하기',
      primaryIcon: Icons.videocam_rounded,
      onPrimary: () => context.pushNamed(AppRoute.tutorialVoice),
      body: [
        // TODO: 노트를 들고 있는 포즈로 교체 예정
        const MascotSceneCard(
          pose: MascotPose.front,
          bubble: '자기소개는 어렵지 않아요!\n오늘 기분부터 가볍게 시작해봐요 😊',
        ),
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.format_list_bulleted_rounded, title: '예시 주제'),
              Gap.h8,
              for (var i = 0;
                  i < TutorialDummy.selfIntroQuestions.length;
                  i++) ...[
                if (i > 0) const Divider(color: AppColors.divider, height: 1),
                IconInfoTile(
                  icon: TutorialDummy.selfIntroQuestions[i].icon,
                  title: TutorialDummy.selfIntroQuestions[i].title,
                  description: TutorialDummy.selfIntroQuestions[i].description,
                  trailing: const Icon(Icons.chevron_right_rounded,
                      color: AppColors.textTertiary),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
