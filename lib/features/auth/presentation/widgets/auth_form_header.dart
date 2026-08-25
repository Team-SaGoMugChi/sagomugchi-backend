import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/mascot_image.dart';

/// Shared header for the signup / social-extra-info forms: a back button, a
/// large title + subtitle on the left, and the mascot peeking top-right.
class AuthFormHeader extends StatelessWidget {
  const AuthFormHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.mascotPose,
    this.showBack = true,
  });

  final String title;
  final String subtitle;
  final MascotPose mascotPose;
  final bool showBack;

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showBack)
              IconButton(
                padding: EdgeInsets.zero,
                alignment: Alignment.centerLeft,
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
                onPressed: () => context.pop(),
              ),
            Gap.h8,
            Padding(
              padding: const EdgeInsets.only(right: 96),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: AppTypography.display),
                  Gap.h8,
                  Text(subtitle, style: AppTypography.bodySecondary),
                ],
              ),
            ),
          ],
        ),
        Positioned(
          top: showBack ? 36 : 0,
          right: -8,
          child: MascotImage(pose: mascotPose, size: 116),
        ),
      ],
    );
  }
}
