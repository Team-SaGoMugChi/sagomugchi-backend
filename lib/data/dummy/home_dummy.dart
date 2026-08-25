/// Data for the home screen's weekly calendar + write card.
///
/// The week strip now reflects the **real current date** ([DateTime.now]):
/// today is highlighted and the strip shows the Sun–Sat week containing it.
/// (The monthly calendar / written-day demo still uses the fixed Jan 2026
/// sample in [CalendarDummy] so the recorded-day states stay demonstrable.)
abstract final class HomeDummy {
  HomeDummy._();

  /// Today, normalized to date-only (no time component).
  static DateTime get today {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  /// The 7 dates shown in the weekly strip, centered on [today]
  /// (today-3 … today … today+3 → today sits in the middle column).
  static List<DateTime> get weekDays =>
      List.generate(7, (i) => today.add(Duration(days: i - 3)));

  /// Days that already have a diary record (shown as a dot). None for the
  /// not-yet-written home; real data would come from the diary repository.
  static final Set<DateTime> recordedDays = {};

  static const String writeCardTitle = '일기를 작성해보세요';
  static const String writeCardSubtitle = '오늘의 감정을 기록하면\n내 마음을 더 잘 이해할 수 있어요';
}
