import 'package:flutter/material.dart';

/// Centralized color tokens for Oddo.
///
/// Single source of truth for every color used across the app. Screens and
/// widgets must reference these tokens (never raw `Color(0x...)`), so that a
/// palette change happens in exactly one place.
///
/// Brand color is #7C5CF6 (a soft, comforting violet). Backgrounds stay white /
/// very-light-grey; only light-lavender tints are allowed as secondary
/// surfaces. (2026-07 파랑 #3182F6 → 보라 테마 전환 — 토큰만 교체)
abstract final class AppColors {
  AppColors._();

  // --- Brand / primary ---------------------------------------------------
  static const Color primary = Color(0xFF7C5CF6);
  static const Color primaryPressed = Color(0xFF6242E0);

  /// Light-lavender card / selected-state background (연보라 카드).
  static const Color primarySoft = Color(0xFFF0EBFE);

  /// Border for soft/selected cards.
  static const Color primarySoftBorder = Color(0xFFD9CDFB);

  // --- Auth / onboarding surfaces ---------------------------------------
  /// Light-lavender background used on splash / auth / onboarding screens.
  static const Color authBackground = Color(0xFFF3F0FB);

  /// Decorative cloud/blob tint layered on the auth background corners.
  static const Color cloud = Color(0xFFE7E1F6);

  /// Kakao brand yellow — used only for the Kakao login icon chip.
  static const Color kakao = Color(0xFFFEE500);

  // --- Surfaces / backgrounds -------------------------------------------
  static const Color background = Color(0xFFFFFFFF);

  /// Very light grey alternative background.
  static const Color backgroundAlt = Color(0xFFF7F8FA);
  static const Color surface = Color(0xFFFFFFFF);

  /// Dim overlay behind modals / bottom sheets.
  static const Color overlayDim = Color(0x80000000);

  // --- Video-call (dark) screens ----------------------------------------
  // Tutorial call practice / baseline measuring / Step1 speaking / counseling.
  static const Color callBackground = Color(0xFF17181C);
  static const Color callSurface = Color(0xFF26282D);
  static const Color callTextPrimary = Color(0xFFFFFFFF);
  static const Color callTextSecondary = Color(0xFFB0B6BE);

  // --- Text --------------------------------------------------------------
  static const Color textStrong = Color(0xFF191F28);
  static const Color textPrimary = Color(0xFF333D4B);
  static const Color textSecondary = Color(0xFF6B7684);
  static const Color textTertiary = Color(0xFF8B95A1);
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  // --- Lines -------------------------------------------------------------
  static const Color border = Color(0xFFE5E8EB);
  static const Color divider = Color(0xFFF2F4F6);

  // --- Semantic ----------------------------------------------------------
  static const Color success = Color(0xFF15C47E);
  static const Color warning = Color(0xFFFFB020);
  static const Color error = Color(0xFFF04452);

  // --- Inactive (e.g. bottom tab) ---------------------------------------
  static const Color inactive = Color(0xFFB0B8C1);
}
