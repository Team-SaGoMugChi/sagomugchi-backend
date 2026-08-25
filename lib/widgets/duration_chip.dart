import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_typography.dart';

/// Small blue pill showing a duration (e.g. "약 2분"). Used by the baseline /
/// tutorial measurement-item lists.
class DurationChip extends StatelessWidget {
  const DurationChip(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadius.chip,
      ),
      child: Text(label,
          style: AppTypography.caption.copyWith(
              color: AppColors.primary, fontWeight: FontWeight.w600)),
    );
  }
}
