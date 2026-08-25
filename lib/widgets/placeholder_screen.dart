import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/constants/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'mascot_image.dart';
import 'oddo_app_bar.dart';
import 'primary_button.dart';

/// How a [PlaceholderAction] navigates.
enum NavMode { push, go, pop }

/// A single navigation choice rendered as a button on a [PlaceholderScreen].
/// During the skeleton phase these encode the documented happy-path flow so
/// the prototype is click-through end to end.
class PlaceholderAction {
  const PlaceholderAction(
    this.label, {
    this.routeName,
    this.mode = NavMode.push,
    this.extra,
    this.primary = true,
    this.onTap,
  });

  /// A back/cancel action that pops the current route.
  const PlaceholderAction.back(this.label)
      : routeName = null,
        mode = NavMode.pop,
        extra = null,
        primary = false,
        onTap = null;

  final String label;
  final String? routeName;
  final NavMode mode;
  final Object? extra;
  final bool primary;

  /// Custom handler (e.g. open a modal). Takes precedence over [mode].
  final VoidCallback? onTap;
}

/// Generic stand-in used for every screen during the skeleton phase.
///
/// Shows the screen's title (+ doc number), an optional mascot, and the
/// forward-navigation buttons. Each real screen is later swapped in by
/// replacing the body — the route wiring stays the same.
class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({
    super.key,
    required this.title,
    this.screenNo,
    this.description,
    this.mascot,
    this.actions = const [],
    this.dark = false,
    this.showAppBar = true,
    this.showBack = true,
    this.appBarTitle,
    this.appBarActions,
  });

  final String title;
  final int? screenNo;
  final String? description;
  final MascotPose? mascot;
  final List<PlaceholderAction> actions;

  /// Video-call style dark background (말하기 / 측정 / 상담 screens).
  final bool dark;
  final bool showAppBar;
  final bool showBack;
  final String? appBarTitle;
  final List<Widget>? appBarActions;

  void _handle(BuildContext context, PlaceholderAction action) {
    if (action.onTap != null) {
      action.onTap!();
      return;
    }
    switch (action.mode) {
      case NavMode.push:
        context.pushNamed(action.routeName!, extra: action.extra);
      case NavMode.go:
        context.goNamed(action.routeName!, extra: action.extra);
      case NavMode.pop:
        if (context.canPop()) context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final bg = dark ? AppColors.callBackground : AppColors.background;
    final titleColor = dark ? AppColors.callTextPrimary : AppColors.textStrong;
    final descColor = dark ? AppColors.callTextSecondary : AppColors.textSecondary;

    return Scaffold(
      backgroundColor: bg,
      appBar: showAppBar
          ? OddoAppBar(
              title: appBarTitle ?? title,
              showBack: showBack,
              actions: appBarActions,
              backgroundColor: bg,
              foregroundColor: titleColor,
            )
          : null,
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.screenH,
                vertical: AppSpacing.xl,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const SizedBox(height: AppSpacing.xxl),
                  if (screenNo != null) _ScreenBadge(no: screenNo!, dark: dark),
                  if (mascot != null) ...[
                    const SizedBox(height: AppSpacing.lg),
                    MascotImage(pose: mascot!, size: 140, onDark: dark),
                  ],
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    title,
                    textAlign: TextAlign.center,
                    style: AppTypography.title.copyWith(color: titleColor),
                  ),
                  if (description != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      description!,
                      textAlign: TextAlign.center,
                      style: AppTypography.body.copyWith(color: descColor),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.xxl),
                ],
              ),
            ),
          ),
          if (actions.isNotEmpty)
            BottomActionBar(
              background: bg,
              children: [
                for (final action in actions)
                  action.primary
                      ? PrimaryButton(
                          label: action.label,
                          onPressed: () => _handle(context, action),
                        )
                      : SizedBox(
                          width: double.infinity,
                          child: TextButton(
                            onPressed: () => _handle(context, action),
                            child: Text(action.label),
                          ),
                        ),
              ],
            ),
        ],
      ),
    );
  }
}

class _ScreenBadge extends StatelessWidget {
  const _ScreenBadge({required this.no, required this.dark});

  final int no;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: dark ? AppColors.callSurface : AppColors.primarySoft,
        borderRadius: AppRadius.chip,
      ),
      child: Text(
        '화면 $no',
        style: AppTypography.caption.copyWith(
          color: dark ? AppColors.callTextSecondary : AppColors.primary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
