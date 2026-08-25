import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/error/app_exception.dart';
import '../../baseline/data/baseline_providers.dart';
import '../data/diary_providers.dart';
import '../data/models/fusion_result.dart';
import 'diary_draft_provider.dart';

/// Step1(말하기)에서 모은 녹음/얼굴 캡처를 baseline과 비교해 감정을 뽑는 상태.
///
/// idle은 `AsyncData(null)`로 표현한다 — 처리 화면 진입 시 자동으로 [submit]을
/// 호출하고, 실패하면 사용자가 재시도 버튼으로 다시 [submit]을 부를 수 있다
/// (baselineUploadController와 같은 모양).
class Step1AnalysisController extends Notifier<AsyncValue<FusionResult?>> {
  @override
  AsyncValue<FusionResult?> build() => const AsyncData(null);

  // STT(Naver CLOVA, Phase 5)가 아직 연동되지 않아서 fusion이 텍스트 감정을
  // 분류할 원문이 없다 — 실제 발화 대신 이 자리표시자를 보낸다. STT가
  // 붙으면 diaryDraftProvider의 transcript(Step1 결과)로 교체.
  static const _placeholderText = '오늘 있었던 일을 편하게 이야기했어요.';

  Future<void> submit() async {
    final draft = ref.read(diaryDraftProvider);
    final voicePath = draft.recordingPath;
    final facePath = draft.faceImagePath;

    if (voicePath == null || facePath == null) {
      state = AsyncError(
        const AppException('말하기 녹음 또는 얼굴 데이터를 찾을 수 없어요. 다시 녹음해주세요.'),
        StackTrace.current,
      );
      return;
    }

    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final baseline = await ref.read(baselineRepositoryProvider).fetchSaved();
      if (baseline == null) {
        throw const AppException('베이스라인 측정 정보를 찾을 수 없어요. 설정에서 다시 측정해주세요.');
      }

      final result = await ref
          .read(diaryAnalysisRepositoryProvider)
          .analyzeStep2(
            text: draft.transcript ?? _placeholderText,
            voiceFilePath: voicePath,
            faceImagePath: facePath,
            baseline: baseline,
          );
      ref.read(diaryDraftProvider.notifier).setFusionResult(result);
      return result;
    });
  }
}

final step1AnalysisControllerProvider =
    NotifierProvider<Step1AnalysisController, AsyncValue<FusionResult?>>(
      Step1AnalysisController.new,
    );
