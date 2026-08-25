import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Soft-blue explainer callout: an icon + bold title + description. Used for
/// "페르소나란?" / "베이스라인이란?" style notes.
class InfoCallout extends StatelessWidget {
  const InfoCallout({
    super.key,
    required this.title,
    required this.description,
    this.icon = Icons.info_outline_rounded,
  });

  final String title;
  final String description;
  final IconData icon;

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
          Icon(icon, size: 20, color: AppColors.primary),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: AppTypography.bodySecondary
                        .copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(description, style: AppTypography.caption),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
