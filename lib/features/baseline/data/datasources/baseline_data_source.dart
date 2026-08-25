import '../models/baseline_profile.dart';

/// Baseline 측정 결과를 AI 서버에 업로드/조회하는 추상화.
abstract interface class BaselineDataSource {
  /// 음성 파일 + 얼굴 이미지를 업로드하고, AI 서버가 계산한 baseline 프로필을 받는다.
  Future<BaselineProfile> upload({
    required String voiceFilePath,
    required String faceImagePath,
  });

  /// 이전에 저장된 baseline 프로필을 읽어온다 — 일기 Step1 분석이 baseline
  /// 대비 Δ를 계산할 때 필요. 아직 측정 전이면 null.
  Future<BaselineProfile?> fetchSaved();
}
