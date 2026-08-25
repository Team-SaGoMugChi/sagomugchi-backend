import '../../../baseline/data/models/baseline_profile.dart';
import '../datasources/diary_analysis_data_source.dart';
import '../models/fusion_result.dart';
import 'diary_analysis_repository.dart';

class DiaryAnalysisRepositoryImpl implements DiaryAnalysisRepository {
  DiaryAnalysisRepositoryImpl(this._dataSource);

  final DiaryAnalysisDataSource _dataSource;

  @override
  Future<FusionResult> analyzeStep2({
    required String text,
    required String voiceFilePath,
    required String faceImagePath,
    required BaselineProfile baseline,
  }) {
    return _dataSource.analyzeStep2(
      text: text,
      voiceFilePath: voiceFilePath,
      faceImagePath: faceImagePath,
      baseline: baseline,
    );
  }
}
