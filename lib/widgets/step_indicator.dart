import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Horizontal numbered stepper used by the 4-step diary-writing flow
/// (말하기 / 확인하기 / 영상 제작 / 상담하기).
class StepIndicator extends StatelessWidget {
  const StepIndicator({
    super.key,
    required this.steps,
    required this.currentIndex,
  });

  final List<String> steps;
  final int currentIndex;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (var i = 0; i < steps.length; i++) ...[
          if (i > 0)
            Expanded(
              child: Container(
                height: 2,
                color: i <= currentIndex ? AppColors.primary : AppColors.border,
              ),
            ),
          _StepNode(
            index: i,
            label: steps[i],
            active: i == currentIndex,
            done: i < currentIndex,
          ),
        ],
      ],
    );
  }
}

class _StepNode extends StatelessWidget {
  const _StepNode({
    required this.index,
    required this.label,
    required this.active,
    required this.done,
  });

  final int index;
  final String label;
  final bool active;
  final bool done;

  @override
  Widget build(BuildContext context) {
    final highlighted = active || done;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: highlighted ? AppColors.primary : AppColors.backgroundAlt,
            border: Border.all(
              color: highlighted ? AppColors.primary : AppColors.border,
            ),
          ),
          alignment: Alignment.center,
          child: done
              ? const Icon(Icons.check_rounded,
                  size: 16, color: AppColors.textOnPrimary)
              : Text(
                  '${index + 1}',
                  style: AppTypography.caption.copyWith(
                    color: highlighted
                        ? AppColors.textOnPrimary
                        : AppColors.textTertiary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: AppTypography.caption.copyWith(
            color: active ? AppColors.primary : AppColors.textTertiary,
            fontWeight: active ? FontWeight.w700 : FontWeight.w400,
          ),
        ),
      ],
    );
  }
}
