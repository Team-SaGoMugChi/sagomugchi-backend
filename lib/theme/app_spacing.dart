import 'package:flutter/widgets.dart';

/// Spacing scale (8pt-based) used for padding, margins and gaps.
///
/// Use these constants instead of hard-coded numbers so spacing stays
/// consistent and tunable from one place.
abstract final class AppSpacing {
  AppSpacing._();

  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 40;

  /// Default horizontal screen padding.
  static const double screenH = 20;

  /// Default vertical screen padding.
  static const double screenV = 16;

  /// Convenience EdgeInsets for the standard screen body.
  static const EdgeInsets screenPadding =
      EdgeInsets.symmetric(horizontal: screenH, vertical: screenV);
}

/// Pre-built vertical/horizontal gap widgets to keep column/row code terse.
abstract final class Gap {
  Gap._();

  static const SizedBox h4 = SizedBox(height: AppSpacing.xxs);
  static const SizedBox h8 = SizedBox(height: AppSpacing.xs);
  static const SizedBox h12 = SizedBox(height: AppSpacing.sm);
  static const SizedBox h16 = SizedBox(height: AppSpacing.md);
  static const SizedBox h20 = SizedBox(height: AppSpacing.lg);
  static const SizedBox h24 = SizedBox(height: AppSpacing.xl);
  static const SizedBox h32 = SizedBox(height: AppSpacing.xxl);

  static const SizedBox w4 = SizedBox(width: AppSpacing.xxs);
  static const SizedBox w8 = SizedBox(width: AppSpacing.xs);
  static const SizedBox w12 = SizedBox(width: AppSpacing.sm);
  static const SizedBox w16 = SizedBox(width: AppSpacing.md);
}
