import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Full-width primary CTA. The design system favors a large rounded button
/// fixed near the bottom of most screens.
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.enabled = true,
    this.loading = false,
    this.leadingIcon,
    this.trailingIcon,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool enabled;
  final bool loading;

  /// Optional icon shown before the label (e.g. a camera for "측정 시작하기").
  final IconData? leadingIcon;

  /// Optional icon shown after the label (e.g. a forward chevron).
  final IconData? trailingIcon;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: (enabled && !loading) ? onPressed : null,
        child: loading
            ? const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: AppColors.textOnPrimary,
                ),
              )
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (leadingIcon != null) ...[
                    Icon(leadingIcon, size: 18),
                    const SizedBox(width: 6),
                  ],
                  Text(label),
                  if (trailingIcon != null) ...[
                    const SizedBox(width: 6),
                    Icon(trailingIcon, size: 18),
                  ],
                ],
              ),
      ),
    );
  }
}

/// Secondary action: full-width outlined button (white fill + primary border)
/// so it stays clearly visible on the light-blue background.
class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    super.key,
    required this.label,
    this.onPressed,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: TextButton(
        onPressed: onPressed,
        style: TextButton.styleFrom(
          backgroundColor: AppColors.surface,
          foregroundColor: AppColors.primary,
          minimumSize: const Size.fromHeight(56),
          textStyle: AppTypography.button,
          side: const BorderSide(color: AppColors.primary, width: 1.5),
          shape: const RoundedRectangleBorder(borderRadius: AppRadius.button),
        ),
        child: Text(label),
      ),
    );
  }
}

/// Bottom-fixed container for CTA buttons, with a top hairline and safe-area
/// padding. Wrap one or more buttons in this for the standard footer.
class BottomActionBar extends StatelessWidget {
  const BottomActionBar({
    super.key,
    required this.children,
    this.background = AppColors.background,
  });

  final List<Widget> children;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: background,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.screenH,
        AppSpacing.sm,
        AppSpacing.screenH,
        AppSpacing.sm,
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < children.length; i++) ...[
              if (i > 0) Gap.h8,
              children[i],
            ],
          ],
        ),
      ),
    );
  }
}
