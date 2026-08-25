import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Soft "TIP" card listing short guidance bullets. Light and dark variants.
class TipCard extends StatelessWidget {
  const TipCard({super.key, required this.tips, this.dark = false});

  final List<String> tips;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final bg = dark ? AppColors.callSurface : AppColors.primarySoft;
    final textColor = dark ? AppColors.callTextSecondary : AppColors.textSecondary;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadius.card),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lightbulb_rounded,
                  size: 16, color: AppColors.warning),
              const SizedBox(width: 6),
              Text('TIP',
                  style: AppTypography.bodySecondary.copyWith(
                      color: AppColors.textStrong,
                      fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          for (final tip in tips)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('· ', style: AppTypography.caption.copyWith(color: textColor)),
                  Expanded(
                    child: Text(tip,
                        style: AppTypography.caption.copyWith(color: textColor)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
