/// Data for the monthly calendar. Uses the **real current month** with today
/// highlighted; recorded days are seeded near today (within the month, today
/// included) so the written/not-written states stay demonstrable. Replace with
/// real diary-date state later.
abstract final class CalendarDummy {
  CalendarDummy._();

  /// Today, normalized to date-only.
  static DateTime get today {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  /// First day of the current month (the grid renders this month).
  static DateTime get month => DateTime(today.year, today.month);

  /// Recorded (already-written) days, within the current month. Today is
  /// intentionally excluded so today defaults to the "write a diary" state;
  /// recent past days are written.
  static Set<DateTime> get recordedDays => {
        for (final delta in [-1, -2, -4, -7, -9])
          today.add(Duration(days: delta)),
      }
          .where((d) => d.year == today.year && d.month == today.month)
          .toSet();

  /// Most recent written day (used as the default for the written-day home and
  /// as the demo record date). Falls back to yesterday if none this month.
  static DateTime get latestRecordedDay {
    final days = recordedDays.toList()..sort();
    return days.isNotEmpty
        ? days.last
        : today.subtract(const Duration(days: 1));
  }

  static bool isRecorded(DateTime date) => recordedDays.any(
        (d) => d.year == date.year && d.month == date.month && d.day == date.day,
      );
}
