import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'primary_button.dart';

/// 화면 우상단 "?" 버튼이 여는 맥락별 도움말 바텀시트.
/// [items]는 그 화면에서 알아두면 좋은 3~4줄.
Future<void> showHelpSheet(
  BuildContext context, {
  required String title,
  required List<String> items,
}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
    ),
    builder: (sheetContext) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: const BoxDecoration(
                    color: AppColors.primarySoft,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.help_outline_rounded,
                      size: 18, color: AppColors.primary),
                ),
                const SizedBox(width: 10),
                Text(title, style: AppTypography.subtitle),
              ],
            ),
            Gap.h16,
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 2),
                      child: Icon(Icons.check_circle_outline_rounded,
                          size: 16, color: AppColors.primary),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(item, style: AppTypography.body)),
                  ],
                ),
              ),
            Gap.h8,
            PrimaryButton(
              label: '확인',
              onPressed: () => Navigator.of(sheetContext).pop(),
            ),
          ],
        ),
      ),
    ),
  );
}
