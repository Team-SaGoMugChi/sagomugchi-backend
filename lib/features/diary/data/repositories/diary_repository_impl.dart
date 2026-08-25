import '../datasources/diary_data_source.dart';
import '../models/counsel_session.dart';
import '../models/diary_entry.dart';
import '../models/emotion_report.dart';
import 'diary_repository.dart';

/// Default repository — delegates to a [DiaryDataSource].
class DiaryRepositoryImpl implements DiaryRepository {
  DiaryRepositoryImpl(this._dataSource);

  final DiaryDataSource _dataSource;

  @override
  Future<List<DiaryEntry>> fetchEntries() => _dataSource.fetchEntries();

  @override
  Future<DiaryEntry?> fetchEntry(DateTime date) =>
      _dataSource.fetchEntry(date);

  @override
  Future<EmotionReport?> fetchReport(DateTime date) =>
      _dataSource.fetchReport(date);

  @override
  Future<CounselSession?> fetchCounsel(DateTime date) =>
      _dataSource.fetchCounsel(date);

  @override
  Future<Set<DateTime>> fetchRecordedDates() =>
      _dataSource.fetchRecordedDates();

  @override
  Future<void> saveRecord({
    required DiaryEntry entry,
    required EmotionReport report,
    required CounselSession counsel,
  }) =>
      _dataSource.saveRecord(entry: entry, report: report, counsel: counsel);
}
