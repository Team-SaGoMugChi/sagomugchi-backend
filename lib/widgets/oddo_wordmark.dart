import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// The "Oddo" wordmark: bold blue logotype with a small heart accent above the
/// trailing letters (as on the splash / login / find-password screens).
class OddoWordmark extends StatelessWidget {
  const OddoWordmark({
    super.key,
    this.fontSize = 40,
    this.withHeart = true,
    this.color = AppColors.primary,
  });

  final double fontSize;
  final bool withHeart;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final heartSize = fontSize * 0.26;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Text(
          'Oddo',
          style: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w800,
            color: color,
            height: 1.0,
            letterSpacing: -0.5,
          ),
        ),
        if (withHeart)
          Positioned(
            right: fontSize * 0.04,
            top: -heartSize * 0.45,
            child: Icon(Icons.favorite, size: heartSize, color: color),
          ),
      ],
    );
  }
}
