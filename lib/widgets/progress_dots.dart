import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Row of progress dots shown under a title on multi-step flows
/// (tutorial, baseline, psych test, persona). The active step is a wider pill.
class ProgressDots extends StatelessWidget {
  const ProgressDots({
    super.key,
    required this.count,
    required this.current,
    this.activeColor = AppColors.primary,
    this.inactiveColor = AppColors.border,
  });

  /// Total number of steps.
  final int count;

  /// Zero-based index of the active step.
  final int current;

  final Color activeColor;
  final Color inactiveColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < count; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: 3),
            width: i == current ? 22 : 8,
            height: 8,
            decoration: BoxDecoration(
              color: i == current ? activeColor : inactiveColor,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
      ],
    );
  }
}
