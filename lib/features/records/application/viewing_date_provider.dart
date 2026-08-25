import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The currently-focused diary date — the single source of truth shared by the
/// home (weekly-bar selection) and the record screens (일기 상세 / 감정 리포트 /
/// 상담 기록).
///
/// Driving the date through a provider (rather than a widget constructor arg)
/// is what makes re-selection work: go_router reuses the home page's State when
/// navigating to the same path, so a constructor arg would only ever be read
/// once. Watching this provider, every dependent screen updates on each change.
/// Defaults to today.
class SelectedDate extends Notifier<DateTime> {
  @override
  DateTime build() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  void set(DateTime date) => state = date;
}

final viewingDateProvider =
    NotifierProvider<SelectedDate, DateTime>(SelectedDate.new);
