import 'package:flutter/material.dart';

import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_typography.dart';

/// White, bordered social-login button: a leading brand badge on the left and
/// a centered label. Brand color stays subtle so the blue primary button keeps
/// the visual emphasis (per the design notes on Kakao styling).
class SocialLoginButton extends StatelessWidget {
  const SocialLoginButton({
    super.key,
    required this.label,
    required this.leading,
    this.onPressed,
  });

  final String label;
  final Widget leading;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: AppRadius.button,
      child: InkWell(
        borderRadius: AppRadius.button,
        onTap: onPressed,
        child: Container(
          height: 56,
          decoration: BoxDecoration(
            borderRadius: AppRadius.button,
            border: Border.all(color: AppColors.border),
          ),
          child: Stack(
            alignment: Alignment.center,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.only(left: 16),
                  child: leading,
                ),
              ),
              Text(
                label,
                style: AppTypography.button.copyWith(
                  color: AppColors.textStrong,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
