import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_typography.dart';

/// Rounded speech bubble for the mascot's lines on the baseline/tutorial
/// scenes. Light and dark variants.
class SpeechBubble extends StatelessWidget {
  const SpeechBubble({super.key, required this.text, this.dark = false});

  final String text;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: dark ? AppColors.callSurface : AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: dark ? null : Border.all(color: AppColors.border),
      ),
      child: Text(
        text,
        style: AppTypography.bodySecondary.copyWith(
          color: dark ? AppColors.callTextPrimary : AppColors.textPrimary,
        ),
      ),
    );
  }
}
