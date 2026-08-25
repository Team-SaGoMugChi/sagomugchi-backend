import '../models/counsel_session.dart';
import '../models/diary_entry.dart';
import '../models/emotion_report.dart';

/// Abstraction over diary/report/counsel data. A dummy implementation backs
/// tests/prototyping; the Firestore implementation is the real one.
abstract interface class DiaryDataSource {
  Future<List<DiaryEntry>> fetchEntries();

  Future<DiaryEntry?> fetchEntry(DateTime date);

  Future<EmotionReport?> fetchReport(DateTime date);

  Future<CounselSession?> fetchCounsel(DateTime date);

  /// Dates (date-only) that already have a diary record — drives the home
  /// weekly bar and both calendars.
  Future<Set<DateTime>> fetchRecordedDates();

  /// Persists one completed write-flow run: the diary + its report + counsel
  /// log, all keyed by the entry's date.
  Future<void> saveRecord({
    required DiaryEntry entry,
    required EmotionReport report,
    required CounselSession counsel,
  });
}
