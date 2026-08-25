import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Typography tokens.
///
/// The app currently uses the platform default font. To switch to a bundled
/// brand font later (e.g. Pretendard / Noto Sans KR), set [fontFamily] in one
/// place and register the font asset in pubspec.yaml — every text style here
/// inherits it automatically.
abstract final class AppTypography {
  AppTypography._();

  /// Set to a registered font family name to apply globally. `null` = system.
  static const String? fontFamily = null;

  static const TextStyle display = TextStyle(
    fontFamily: fontFamily,
    fontSize: 26,
    height: 1.35,
    fontWeight: FontWeight.w700,
    color: AppColors.textStrong,
  );

  static const TextStyle title = TextStyle(
    fontFamily: fontFamily,
    fontSize: 22,
    height: 1.4,
    fontWeight: FontWeight.w700,
    color: AppColors.textStrong,
  );

  static const TextStyle subtitle = TextStyle(
    fontFamily: fontFamily,
    fontSize: 18,
    height: 1.45,
    fontWeight: FontWeight.w600,
    color: AppColors.textStrong,
  );

  static const TextStyle bodyLarge = TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    height: 1.5,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  static const TextStyle body = TextStyle(
    fontFamily: fontFamily,
    fontSize: 15,
    height: 1.5,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodySecondary = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    height: 1.5,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: fontFamily,
    fontSize: 12,
    height: 1.4,
    fontWeight: FontWeight.w400,
    color: AppColors.textTertiary,
  );

  static const TextStyle button = TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    height: 1.2,
    fontWeight: FontWeight.w600,
    color: AppColors.textOnPrimary,
  );

  /// Maps tokens onto Material's [TextTheme] so default widgets pick them up.
  static const TextTheme textTheme = TextTheme(
    displaySmall: display,
    headlineSmall: title,
    titleLarge: subtitle,
    titleMedium: subtitle,
    bodyLarge: bodyLarge,
    bodyMedium: body,
    bodySmall: bodySecondary,
    labelLarge: button,
    labelSmall: caption,
  );
}
