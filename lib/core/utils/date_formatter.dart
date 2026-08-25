/// Korean date/time formatting helpers.
///
/// Implemented with explicit Korean label tables (rather than locale-dependent
/// `intl` symbols) so they work offline without `initializeDateFormatting`.
abstract final class DateFormatter {
  DateFormatter._();

  static const List<String> _weekdaysKo = [
    '월', '화', '수', '목', '금', '토', '일', // DateTime.weekday is 1=Mon..7=Sun
  ];

  /// `1월 14일`
  static String monthDay(DateTime date) => '${date.month}월 ${date.day}일';

  /// `2026년 1월`
  static String yearMonth(DateTime date) => '${date.year}년 ${date.month}월';

  /// `수` (single-char weekday)
  static String weekday(DateTime date) => _weekdaysKo[date.weekday - 1];

  /// `2026년 1월 14일 수요일`
  static String fullKoreanDate(DateTime date) =>
      '${date.year}년 ${date.month}월 ${date.day}일 ${weekday(date)}요일';

  /// `2026-07-11` — Firestore 날짜 문서 id 규약 (FIRESTORE_SCHEMA.md).
  static String dateKey(DateTime date) {
    final m = date.month.toString().padLeft(2, '0');
    final d = date.day.toString().padLeft(2, '0');
    return '${date.year}-$m-$d';
  }

  /// `2004.03.15` (birth-date style)
  static String dotted(DateTime date) {
    final m = date.month.toString().padLeft(2, '0');
    final d = date.day.toString().padLeft(2, '0');
    return '${date.year}.$m.$d';
  }

  /// `18:42`
  static String hhmm(DateTime date) {
    final h = date.hour.toString().padLeft(2, '0');
    final m = date.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }
}
