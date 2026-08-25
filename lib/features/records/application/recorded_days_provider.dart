import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config_provider.dart';
import '../../../data/dummy/calendar_dummy.dart';
import '../../auth/application/auth_controller.dart';
import '../../diary/data/diary_providers.dart';

/// Set of days that already have a diary record (date-only) — watched by the
/// home, the weekly bar, and the monthly calendar.
///
/// Source of truth is Firestore (`users/{uid}/diaries` doc ids): the set is
/// (re)loaded whenever the logged-in user changes, and grows immediately via
/// [markRecorded] when a new diary is completed (the doc itself is saved by
/// the write flow). Dummy mode (tests/prototyping) seeds from [CalendarDummy].
class RecordedDays extends Notifier<Set<DateTime>> {
  @override
  Set<DateTime> build() {
    if (ref.watch(appConfigProvider).useDummyData) {
      return {...CalendarDummy.recordedDays};
    }
    // Rebuilds on login/logout; kick the async load for the new session.
    final user = ref.watch(authControllerProvider.select((s) => s.user));
    if (user != null) _load();
    return {};
  }

  Future<void> _load() async {
    try {
      final days =
          await ref.read(diaryRepositoryProvider).fetchRecordedDates();
      state = {...days};
    } catch (_) {
      // Offline/stale-session load failures just leave the set empty; the
      // calendar shows no written days until the next successful load.
    }
  }

  static DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

  /// Marks [date] as recorded. Emits a new set so listeners rebuild.
  void markRecorded(DateTime date) {
    state = {...state, _dateOnly(date)};
  }

  bool isRecorded(DateTime date) => state.contains(_dateOnly(date));
}

final recordedDaysProvider =
    NotifierProvider<RecordedDays, Set<DateTime>>(RecordedDays.new);
