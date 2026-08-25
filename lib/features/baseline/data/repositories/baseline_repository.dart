import '../models/baseline_profile.dart';

abstract interface class BaselineRepository {
  /// 음성/얼굴 baseline 측정을 제출하고 저장된 프로필을 돌려받는다.
  Future<BaselineProfile> submitMeasurement({
    required String voiceFilePath,
    required String faceImagePath,
  });

  /// 이전에 저장된 baseline 프로필을 읽어온다. 아직 측정 전이면 null.
  Future<BaselineProfile?> fetchSaved();
}
