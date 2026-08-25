import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../features/records/application/viewing_date_provider.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/primary_button.dart';

/// Screen 35 — 일기 작성 시작 확인 모달. Centered card confirming writing for
/// [date] → Step 1 말하기 안내. On 시작하기, [date] becomes the focused diary
/// date so the whole write flow (and the final 기록 완료) targets it.
Future<void> showDiaryStartModal(BuildContext context, WidgetRef ref,
    {DateTime? date}) {
  final target = date ?? DateTime.now();
  final writeDate = DateTime(target.year, target.month, target.day);
  final label = date != null ? DateFormatter.monthDay(date) : '오늘';
  return showDialog<void>(
    context: context,
    builder: (dialogContext) => Dialog(
      backgroundColor: AppColors.surface,
      elevation: 0,
      insetPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.card),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg, AppSpacing.xl, AppSpacing.lg, AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('$label 일기를 작성할까요?',
                textAlign: TextAlign.center, style: AppTypography.subtitle),
            Gap.h8,
            const Text('AI와 대화하며\n오늘의 감정을 기록해볼게요.',
                textAlign: TextAlign.center,
                style: AppTypography.bodySecondary),
            Gap.h24,
            PrimaryButton(
              label: '시작하기',
              onPressed: () {
                ref.read(viewingDateProvider.notifier).set(writeDate);
                Navigator.of(dialogContext).pop();
                context.pushNamed(AppRoute.diaryStep1Intro);
              },
            ),
            Gap.h8,
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('취소'),
            ),
          ],
        ),
      ),
    ),
  );
}
