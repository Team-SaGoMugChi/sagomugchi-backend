import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/duration_chip.dart';
import '../../../../widgets/icon_info_tile.dart';
import '../../../../widgets/mascot_scene_card.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/security_card.dart';
import '../../../../widgets/tip_card.dart';
import '../widgets/tutorial_step_scaffold.dart';

/// Screen 15 — 튜토리얼 5/5 측정 방식 안내 및 완료. → 튜토리얼 완료.
class TutorialMethodScreen extends StatelessWidget {
  const TutorialMethodScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return TutorialStepScaffold(
      appBarTitle: '튜토리얼 5/5',
      current: 4,
      stepLabel: '측정 방식 안내 및 완료',
      headline: '이제 첫 측정을 시작할 차례예요!',
      subtitle: '얼굴 표정과 음성 데이터를 수집해\n당신만의 감정 기준을 만들 거예요.',
      primaryLabel: '튜토리얼 완료하기',
      primaryIcon: Icons.videocam_rounded,
      onPrimary: () => context.pushNamed(AppRoute.tutorialDone),
      body: [
        // TODO: 체크리스트를 들고 있는 포즈로 교체 예정
        const MascotSceneCard(
          pose: MascotPose.clipboard,
          bubble: '자연스럽게 이야기하고\n다양한 표정을 지어주면\n더 정확한 분석이 가능해요!',
        ),
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.checklist_rounded, title: '측정 구성'),
              Gap.h8,
              for (var i = 0; i < BaselineDummy.measureItems.length; i++) ...[
                if (i > 0) const Divider(color: AppColors.divider, height: 1),
                IconInfoTile(
                  icon: BaselineDummy.measureItems[i].icon,
                  title: BaselineDummy.measureItems[i].title,
                  description: BaselineDummy.measureItems[i].description,
                  trailing: DurationChip(BaselineDummy.measureItems[i].duration),
                ),
              ],
            ],
          ),
        ),
        const SecurityCard(
          title: '개인정보 보호 안내',
          description: '모든 데이터는 안전하게 보호되며, 감정 분석에만 사용돼요.',
        ),
        const TipCard(tips: BaselineDummy.introTips),
      ],
    );
  }
}
