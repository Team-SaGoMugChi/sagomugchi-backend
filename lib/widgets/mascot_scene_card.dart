import 'package:flutter/material.dart';

import '../core/constants/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import 'mascot_image.dart';
import 'speech_bubble.dart';

/// Illustration panel showing the mascot in a soft "room" card with an optional
/// speech bubble — used on the baseline and tutorial guidance screens.
class MascotSceneCard extends StatelessWidget {
  const MascotSceneCard({
    super.key,
    required this.pose,
    this.bubble,
    this.dark = false,
  });

  final MascotPose pose;
  final String? bubble;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: dark ? AppColors.callSurface : AppColors.primarySoft,
        borderRadius: AppRadius.card,
      ),
      child: Row(
        children: [
          MascotImage(pose: pose, size: 96, onDark: dark),
          if (bubble != null) ...[
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: SpeechBubble(text: bubble!, dark: dark)),
          ],
        ],
      ),
    );
  }
}
