import 'package:flutter/material.dart';

import '../../../../core/utils/date_formatter.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';

/// Horizontal week strip: weekday labels + date cells. The selected day gets a
/// blue ring; today's label reads "오늘"; days with a record show a dot.
class WeeklyCalendar extends StatelessWidget {
  const WeeklyCalendar({
    super.key,
    required this.days,
    required this.today,
    required this.selected,
    this.recordedDays = const {},
    this.onSelect,
  });

  final List<DateTime> days;
  final DateTime today;
  final DateTime selected;
  final Set<DateTime> recordedDays;
  final ValueChanged<DateTime>? onSelect;

  bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (final day in days) Expanded(child: _cell(day)),
      ],
    );
  }

  Widget _cell(DateTime day) {
    final isToday = _sameDay(day, today);
    final isSelected = _sameDay(day, selected);
    final hasRecord = recordedDays.any((d) => _sameDay(d, day));

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => onSelect?.call(day),
      child: Column(
        children: [
          Text(
            isToday ? '오늘' : DateFormatter.weekday(day),
            style: AppTypography.caption.copyWith(
              color: isToday ? AppColors.primary : AppColors.textTertiary,
              fontWeight: isToday ? FontWeight.w700 : FontWeight.w400,
            ),
          ),
          const SizedBox(height: 6),
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isSelected ? AppColors.primary : Colors.transparent,
              border: isSelected
                  ? null
                  : Border.all(color: Colors.transparent),
            ),
            alignment: Alignment.center,
            child: Text(
              '${day.day}',
              style: AppTypography.body.copyWith(
                color: isSelected ? AppColors.textOnPrimary : AppColors.textStrong,
                fontWeight:
                    isSelected || isToday ? FontWeight.w700 : FontWeight.w400,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Container(
            width: 5,
            height: 5,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: hasRecord ? AppColors.primary : Colors.transparent,
            ),
          ),
        ],
      ),
    );
  }
}
