import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Labeled multi-node progress bar (dots connected by lines + labels below),
/// used in the baseline header ("안내 진행 — 측정 진행"). Has a dark variant
/// for the video-call measuring screen.
class StepProgressBar extends StatelessWidget {
  const StepProgressBar({
    super.key,
    required this.labels,
    required this.currentIndex,
    this.onDark = false,
  });

  final List<String> labels;
  final int currentIndex;
  final bool onDark;

  Color get _active => AppColors.primary;
  Color get _inactive =>
      onDark ? AppColors.callSurface : AppColors.primarySoftBorder;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            for (var i = 0; i < labels.length; i++) ...[
              if (i > 0)
                Expanded(
                  child: Container(
                    height: 3,
                    color: i <= currentIndex ? _active : _inactive,
                  ),
                ),
              _dot(i <= currentIndex),
            ],
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            for (var i = 0; i < labels.length; i++)
              Expanded(
                child: Text(
                  labels[i],
                  textAlign: i == 0
                      ? TextAlign.left
                      : i == labels.length - 1
                          ? TextAlign.right
                          : TextAlign.center,
                  style: AppTypography.caption.copyWith(
                    color: i <= currentIndex
                        ? _active
                        : (onDark
                            ? AppColors.callTextSecondary
                            : AppColors.textTertiary),
                    fontWeight:
                        i == currentIndex ? FontWeight.w700 : FontWeight.w400,
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Widget _dot(bool active) {
    return Container(
      width: 14,
      height: 14,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: active ? _active : _inactive,
        border: Border.all(
          color: active ? _active : _inactive,
          width: 2,
        ),
      ),
      child: active
          ? const Icon(Icons.check, size: 9, color: AppColors.textOnPrimary)
          : null,
    );
  }
}
