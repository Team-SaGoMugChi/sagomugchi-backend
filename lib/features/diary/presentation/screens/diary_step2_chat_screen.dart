import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../data/dummy/diary_flow_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/chat_bubble.dart';
import '../../../../widgets/primary_button.dart';
import '../../data/models/counsel_session.dart';
import '../widgets/diary_step_header.dart';

/// Screen 40 — Step 2. 추가 질문 채팅. Chatbot asks follow-up questions to
/// enrich the diary → Step 3.
class DiaryStep2ChatScreen extends StatelessWidget {
  const DiaryStep2ChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              const DiaryStepHeader(title: 'Step 2. 추가 질문', currentStep: 1),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.md),
                  children: [
                    for (final msg in DiaryFlowDummy.step2Chat)
                      ChatBubble(
                          fromOddo: msg.speaker == CounselSpeaker.oddo,
                          text: msg.text),
                  ],
                ),
              ),
              const _InputBar(),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: SafeArea(
                  top: false,
                  child: PrimaryButton(
                    label: '답변 완료하고 다음 단계로',
                    onPressed: () =>
                        context.pushNamed(AppRoute.diaryStep3VideoLoading),
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

/// Decorative chat input bar (no real input wired for the prototype).
class _InputBar extends StatelessWidget {
  const _InputBar();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text('메시지를 입력해주세요',
                  style: AppTypography.body
                      .copyWith(color: AppColors.textTertiary)),
            ),
            const Icon(Icons.mic_none_rounded,
                size: 20, color: AppColors.textTertiary),
            const SizedBox(width: 12),
            const Icon(Icons.send_rounded, size: 20, color: AppColors.primary),
          ],
        ),
      ),
    );
  }
}
