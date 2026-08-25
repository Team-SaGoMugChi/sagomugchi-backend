import 'package:flutter/material.dart';

import '../../../../data/dummy/auth_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_typography.dart';

/// Segmented selector for 성별 (여성 / 남성 / 선택 안 함). Manages its own
/// selection — purely UI for the prototype.
class GenderSelector extends StatefulWidget {
  const GenderSelector({
    super.key,
    this.options = AuthDummy.genders,
    this.onChanged,
  });

  final List<String> options;
  final ValueChanged<String>? onChanged;

  @override
  State<GenderSelector> createState() => _GenderSelectorState();
}

class _GenderSelectorState extends State<GenderSelector> {
  int? _selected;

  IconData _iconFor(String label) {
    if (label.contains('여')) return Icons.female_rounded;
    if (label.contains('남')) return Icons.male_rounded;
    return Icons.remove_rounded;
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (var i = 0; i < widget.options.length; i++) ...[
          if (i > 0) const SizedBox(width: 8),
          Expanded(child: _segment(i)),
        ],
      ],
    );
  }

  Widget _segment(int index) {
    final label = widget.options[index];
    final selected = _selected == index;
    return GestureDetector(
      onTap: () {
        setState(() => _selected = index);
        widget.onChanged?.call(label);
      },
      child: Container(
        height: 52,
        decoration: BoxDecoration(
          color: selected ? AppColors.primarySoft : AppColors.surface,
          borderRadius: AppRadius.button,
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              _iconFor(label),
              size: 16,
              color: selected ? AppColors.primary : AppColors.textTertiary,
            ),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.bodySecondary.copyWith(
                  color: selected ? AppColors.primary : AppColors.textSecondary,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
