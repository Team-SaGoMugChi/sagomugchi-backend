import 'package:flutter/material.dart';

import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';

/// A single emotion-baseline summary metric tile (icon + label + value) on the
/// completion screen.
class MetricTile extends StatelessWidget {
  const MetricTile({super.key, required this.metric});

  final BaselineMetric metric;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.card,
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(metric.icon, size: 16, color: metric.color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(metric.label,
                    style: AppTypography.caption,
                    overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            metric.value,
            style: AppTypography.subtitle.copyWith(color: metric.color),
          ),
        ],
      ),
    );
  }
}
