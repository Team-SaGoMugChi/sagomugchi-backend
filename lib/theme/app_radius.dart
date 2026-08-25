import 'package:flutter/widgets.dart';

/// Corner-radius tokens. Cards use 20~28; buttons use the large pill-ish radius.
abstract final class AppRadius {
  AppRadius._();

  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double xxl = 28;

  /// Fully rounded (chips, avatars, pills).
  static const double pill = 999;

  static const Radius rSm = Radius.circular(sm);
  static const Radius rMd = Radius.circular(md);
  static const Radius rLg = Radius.circular(lg);
  static const Radius rXl = Radius.circular(xl);

  static const BorderRadius card = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius button = BorderRadius.all(Radius.circular(md));
  static const BorderRadius chip = BorderRadius.all(Radius.circular(pill));
  static const BorderRadius sheet = BorderRadius.vertical(top: Radius.circular(xxl));
}
