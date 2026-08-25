import '../../../baseline/data/models/baseline_profile.dart';
import '../models/fusion_result.dart';

/// 일기 Step1(말하기)에서 모은 음성/얼굴을 baseline과 비교해 감정을 뽑는
/// 추상화 — AI 서버 `POST /diary/step2/analyze` 하나를 감싼다.
abstract interface class DiaryAnalysisDataSource {
  /// [text]는 Step1 STT 결과(현재는 Naver CLOVA 연동 전이라 임시 텍스트,
  /// Phase 5에서 실제 STT 결과로 교체) — fusion이 텍스트 감정 분류에 쓴다.
  Future<FusionResult> analyzeStep2({
    required String text,
    required String voiceFilePath,
    required String faceImagePath,
    required BaselineProfile baseline,
  });
}
