import '../../../../core/constants/app_durations.dart';
import '../../../baseline/data/models/baseline_profile.dart';
import '../models/fusion_result.dart';
import 'diary_analysis_data_source.dart';

/// 테스트/더미 모드용 — 실제 업로드 없이 그럴듯한 fusion 결과를 즉시 반환한다.
class DiaryAnalysisDummyDataSource implements DiaryAnalysisDataSource {
  @override
  Future<FusionResult> analyzeStep2({
    required String text,
    required String voiceFilePath,
    required String faceImagePath,
    required BaselineProfile baseline,
  }) async {
    await Future<void>.delayed(AppDurations.dummyLatency);
    return const FusionResult(
      emotionKeywords: ['속상함', '후회', '답답함', '미안함'],
      emotionScores: {'속상함': 42, '후회': 28, '답답함': 18, '평온': 12},
      emotionIntensity: 72,
      textEmotionScores: {'속상함': 0.42, '후회': 0.28, '답답함': 0.18, '평온': 0.12},
      voiceDelta: {
        'pitchMean': FeatureDelta(
          baselineValue: 180,
          currentValue: 205,
          delta: 25,
          relativeDelta: 0.14,
        ),
      },
      faceDelta: {
        'mouthAspectRatio': FeatureDelta(
          baselineValue: 0.1,
          currentValue: 0.16,
          delta: 0.06,
          relativeDelta: 0.6,
        ),
      },
    );
  }
}
