import '../../../../core/constants/app_durations.dart';
import '../models/baseline_profile.dart';
import 'baseline_data_source.dart';

/// 테스트/더미 모드용 — 실제 업로드 없이 그럴듯한 프로필을 즉시 반환한다.
class BaselineDummyDataSource implements BaselineDataSource {
  @override
  Future<BaselineProfile> upload({
    required String voiceFilePath,
    required String faceImagePath,
  }) async {
    await Future<void>.delayed(AppDurations.dummyLatency);
    return BaselineProfile(
      voice: const {'pitchMean': 180.0, 'energyMean': 0.3, 'speechRate': 3.5},
      face: const {'eyeAspectRatio': 0.28, 'mouthAspectRatio': 0.1},
      measuredAt: DateTime.now(),
    );
  }

  @override
  Future<BaselineProfile?> fetchSaved() async {
    await Future<void>.delayed(AppDurations.dummyLatency);
    return BaselineProfile(
      voice: const {'pitchMean': 180.0, 'energyMean': 0.3, 'speechRate': 3.5},
      face: const {'eyeAspectRatio': 0.28, 'mouthAspectRatio': 0.1},
      measuredAt: DateTime.now().subtract(const Duration(days: 3)),
    );
  }
}
