import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Boxed "data is safe" reassurance card (title + description + lock), used on
/// the baseline screens. Supports a dark variant for the video-call screen.
class SecurityCard extends StatelessWidget {
  const SecurityCard({
    super.key,
    this.title = '안전하고 비밀이 보장돼요',
    this.description = '모든 데이터는 안전하게 보호되며, 나만을 위한 분석에 사용돼요.',
    this.dark = false,
  });

  final String title;
  final String description;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final bg = dark ? AppColors.callSurface : AppColors.primarySoft;
    final titleColor = dark ? AppColors.callTextPrimary : AppColors.textStrong;
    final descColor = dark ? AppColors.callTextSecondary : AppColors.textSecondary;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadius.card),
      child: Row(
        children: [
          const Icon(Icons.verified_user_rounded,
              size: 22, color: AppColors.primary),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: AppTypography.bodySecondary.copyWith(
                        color: titleColor, fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(description,
                    style: AppTypography.caption.copyWith(color: descColor)),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.xs),
          Icon(Icons.lock_rounded, size: 16, color: descColor),
        ],
      ),
    );
  }
}
