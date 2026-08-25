import 'package:flutter/material.dart';

import '../../../../core/utils/date_formatter.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';

/// Reusable month grid: month nav + weekday header + date cells. A single
/// widget renders both the written/not-written states — recorded days get a
/// blue tint, today gets a ring, the selected day gets a solid fill.
class MonthlyCalendar extends StatelessWidget {
  const MonthlyCalendar({
    super.key,
    required this.month,
    required this.today,
    required this.selected,
    required this.onSelect,
    this.recordedDays = const {},
    this.onPrevMonth,
    this.onNextMonth,
  });

  /// Any date within the month to render (day is ignored).
  final DateTime month;
  final DateTime today;
  final DateTime selected;
  final ValueChanged<DateTime> onSelect;
  final Set<DateTime> recordedDays;
  final VoidCallback? onPrevMonth;
  final VoidCallback? onNextMonth;

  static const List<String> _weekdayLabels = ['일', '월', '화', '수', '목', '금', '토'];

  bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  @override
  Widget build(BuildContext context) {
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final firstWeekday = DateTime(month.year, month.month, 1).weekday; // Mon=1..Sun=7
    final leadingBlanks = firstWeekday % 7; // Sun-first grid

    // Build the flat cell list (leading blanks + day numbers), then chunk by 7.
    final cells = <int?>[
      for (var i = 0; i < leadingBlanks; i++) null,
      for (var d = 1; d <= daysInMonth; d++) d,
    ];
    while (cells.length % 7 != 0) {
      cells.add(null);
    }

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.card,
        boxShadow: [
          BoxShadow(color: Color(0x0A000000), blurRadius: 16, offset: Offset(0, 4)),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton(
                icon: const Icon(Icons.chevron_left_rounded),
                color: AppColors.textSecondary,
                onPressed: onPrevMonth,
              ),
              Text(DateFormatter.yearMonth(month),
                  style: AppTypography.subtitle),
              IconButton(
                icon: const Icon(Icons.chevron_right_rounded),
                color: AppColors.textSecondary,
                onPressed: onNextMonth,
              ),
            ],
          ),
          Row(
            children: [
              for (var i = 0; i < 7; i++)
                Expanded(
                  child: Center(
                    child: Text(
                      _weekdayLabels[i],
                      style: AppTypography.caption.copyWith(color: _weekdayColor(i)),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          for (var w = 0; w < cells.length ~/ 7; w++)
            Row(
              children: [
                for (var i = 0; i < 7; i++) _buildCell(cells[w * 7 + i], i),
              ],
            ),
        ],
      ),
    );
  }

  Color _weekdayColor(int column) {
    if (column == 0) return AppColors.error; // Sunday
    if (column == 6) return AppColors.primary; // Saturday
    return AppColors.textSecondary;
  }

  Widget _buildCell(int? day, int column) {
    if (day == null) {
      return const Expanded(child: SizedBox(height: 44));
    }
    final date = DateTime(month.year, month.month, day);
    final isSelected = _sameDay(date, selected);
    final isToday = _sameDay(date, today);
    final isRecorded = recordedDays.any((d) => _sameDay(d, date));

    BoxDecoration? deco;
    if (isSelected) {
      deco = const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle);
    } else if (isToday) {
      deco = BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.primary, width: 1.5),
      );
    } else if (isRecorded) {
      deco = BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      );
    }

    final textColor = isSelected
        ? AppColors.textOnPrimary
        : _weekdayColor(column) == AppColors.textSecondary
            ? AppColors.textStrong
            : _weekdayColor(column);

    return Expanded(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => onSelect(date),
        child: Container(
          height: 44,
          alignment: Alignment.center,
          child: Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: deco,
            child: Text(
              '$day',
              style: AppTypography.bodySecondary.copyWith(
                color: textColor,
                fontWeight: isSelected || isToday ? FontWeight.w700 : FontWeight.w400,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
