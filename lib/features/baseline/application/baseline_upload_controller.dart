import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/error/app_exception.dart';
import '../data/baseline_providers.dart';
import '../data/models/baseline_profile.dart';
import 'baseline_face_image_provider.dart';
import 'baseline_recording_provider.dart';

/// 측정 화면에서 모아둔 음성/얼굴 파일을 AI 서버에 업로드하는 상태.
///
/// idle은 `AsyncData(null)`로 표현한다 — 분석 화면 진입 시 자동으로 [submit]을
/// 호출하고, 실패하면 사용자가 재시도 버튼으로 다시 [submit]을 부를 수 있다.
class BaselineUploadController extends Notifier<AsyncValue<BaselineProfile?>> {
  @override
  AsyncValue<BaselineProfile?> build() => const AsyncData(null);

  Future<void> submit() async {
    final voicePath = ref.read(baselineRecordingProvider);
    final facePath = ref.read(baselineFaceImageProvider);

    if (voicePath == null || facePath == null) {
      state = AsyncError(
        const AppException('음성 또는 얼굴 데이터를 찾을 수 없어요. 측정을 다시 진행해주세요.'),
        StackTrace.current,
      );
      return;
    }

    state = const AsyncLoading();
    state = await AsyncValue.guard(() {
      return ref.read(baselineRepositoryProvider).submitMeasurement(
            voiceFilePath: voicePath,
            faceImagePath: facePath,
          );
    });
  }
}

final baselineUploadControllerProvider = NotifierProvider<
    BaselineUploadController, AsyncValue<BaselineProfile?>>(
  BaselineUploadController.new,
);
