import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Small section heading inside a card: a primary-colored icon + bold label.
class CardSectionHeader extends StatelessWidget {
  const CardSectionHeader({super.key, required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: AppColors.primary),
        const SizedBox(width: 6),
        Text(
          title,
          style: AppTypography.bodySecondary.copyWith(
              color: AppColors.textStrong, fontWeight: FontWeight.w700),
        ),
      ],
    );
  }
}
