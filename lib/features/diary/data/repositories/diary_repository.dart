import '../models/counsel_session.dart';
import '../models/diary_entry.dart';
import '../models/emotion_report.dart';

/// What the app needs for diary records, independent of the data source.
abstract interface class DiaryRepository {
  Future<List<DiaryEntry>> fetchEntries();

  Future<DiaryEntry?> fetchEntry(DateTime date);

  Future<EmotionReport?> fetchReport(DateTime date);

  Future<CounselSession?> fetchCounsel(DateTime date);

  Future<Set<DateTime>> fetchRecordedDates();

  Future<void> saveRecord({
    required DiaryEntry entry,
    required EmotionReport report,
    required CounselSession counsel,
  });
}
