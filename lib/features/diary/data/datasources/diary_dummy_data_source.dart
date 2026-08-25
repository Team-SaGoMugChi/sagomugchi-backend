import '../../../../core/constants/app_durations.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/calendar_dummy.dart';
import '../../../../data/dummy/dummy_seed.dart';
import '../models/counsel_session.dart';
import '../models/diary_entry.dart';
import '../models/emotion_report.dart';
import 'diary_data_source.dart';

/// In-memory diary data backed by [DummySeed]. Saved records live in maps so
/// the session behaves like the real thing (until restart).
class DiaryDummyDataSource implements DiaryDataSource {
  final Map<String, DiaryEntry> _entries = {
    DateFormatter.dateKey(DummySeed.diaryJan14.date): DummySeed.diaryJan14,
  };
  final Map<String, EmotionReport> _reports = {
    DateFormatter.dateKey(DummySeed.reportJan14.date): DummySeed.reportJan14,
  };
  final Map<String, CounselSession> _counsels = {
    DateFormatter.dateKey(DummySeed.counselJan14.date): DummySeed.counselJan14,
  };

  Future<void> _delay() => Future<void>.delayed(AppDurations.dummyLatency);

  @override
  Future<List<DiaryEntry>> fetchEntries() async {
    await _delay();
    return _entries.values.toList();
  }

  @override
  Future<DiaryEntry?> fetchEntry(DateTime date) async {
    await _delay();
    return _entries[DateFormatter.dateKey(date)];
  }

  @override
  Future<EmotionReport?> fetchReport(DateTime date) async {
    await _delay();
    return _reports[DateFormatter.dateKey(date)];
  }

  @override
  Future<CounselSession?> fetchCounsel(DateTime date) async {
    await _delay();
    return _counsels[DateFormatter.dateKey(date)];
  }

  @override
  Future<Set<DateTime>> fetchRecordedDates() async {
    await _delay();
    return {
      ...CalendarDummy.recordedDays,
      for (final e in _entries.values)
        DateTime(e.date.year, e.date.month, e.date.day),
    };
  }

  @override
  Future<void> saveRecord({
    required DiaryEntry entry,
    required EmotionReport report,
    required CounselSession counsel,
  }) async {
    await _delay();
    final key = DateFormatter.dateKey(entry.date);
    _entries[key] = entry;
    _reports[key] = report;
    _counsels[key] = counsel;
  }
}
