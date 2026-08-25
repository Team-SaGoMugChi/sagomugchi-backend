import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Light-blue app background with soft decorative cloud blobs in the top
/// corners. Shared chrome for splash / auth / home / onboarding / baseline
/// screens. Wrap a screen body in this.
class AppBackground extends StatelessWidget {
  const AppBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.authBackground,
      child: Stack(
        children: [
          Positioned(top: -70, left: -50, child: _blob(190)),
          Positioned(top: -30, right: -60, child: _blob(220)),
          Positioned(
            top: 150,
            left: 28,
            child: Icon(Icons.favorite,
                size: 14, color: AppColors.cloud.withValues(alpha: 0.9)),
          ),
          Positioned(
            top: 110,
            right: 40,
            child: Icon(Icons.favorite,
                size: 10, color: AppColors.cloud.withValues(alpha: 0.9)),
          ),
          child,
        ],
      ),
    );
  }

  Widget _blob(double size) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: AppColors.cloud,
        shape: BoxShape.circle,
      ),
    );
  }
}
