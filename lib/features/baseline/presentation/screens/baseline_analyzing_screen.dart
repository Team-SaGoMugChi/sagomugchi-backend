import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../application/baseline_upload_controller.dart';

/// Screen 20 — Baseline 분석 중. 측정 화면에서 모은 음성/얼굴 파일을 AI 서버에
/// 업로드하고, 성공하면 완료 화면으로 넘어간다. 실패하면 재시도할 수 있다.
class BaselineAnalyzingScreen extends ConsumerStatefulWidget {
  const BaselineAnalyzingScreen({super.key});

  @override
  ConsumerState<BaselineAnalyzingScreen> createState() =>
      _BaselineAnalyzingScreenState();
}

class _BaselineAnalyzingScreenState
    extends ConsumerState<BaselineAnalyzingScreen> {
  @override
  void initState() {
    super.initState();
    // initState 안에서 바로 submit()을 부르면 상태 변경이 빌드 도중 일어날 수 있어
    // 다음 마이크로태스크로 미룬다.
    Future.microtask(
        () => ref.read(baselineUploadControllerProvider.notifier).submit());
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(baselineUploadControllerProvider, (previous, next) {
      final profile = next.value;
      if (profile != null && mounted) {
        context.pushReplacementNamed(AppRoute.baselineDone);
      }
    });

    final uploadState = ref.watch(baselineUploadControllerProvider);

    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
              child: uploadState.hasError
                  ? _ErrorContent(
                      message: _errorMessage(uploadState.error),
                      onRetry: () => ref
                          .read(baselineUploadControllerProvider.notifier)
                          .submit(),
                    )
                  : const _LoadingContent(),
            ),
          ),
        ),
      ),
    );
  }

  String _errorMessage(Object? error) {
    if (error is AppException) return error.message;
    return '분석 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.';
  }
}

class _LoadingContent extends StatelessWidget {
  const _LoadingContent();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // TODO: 노트북을 보며 분석하는 포즈로 교체 예정 (character_sheet 15.노트북)
        const MascotImage(pose: MascotPose.thinking, size: 150),
        Gap.h20,
        const SizedBox(
          width: 30,
          height: 30,
          child: CircularProgressIndicator(strokeWidth: 3, color: AppColors.primary),
        ),
        Gap.h20,
        const Text('첫 감정 기준을 정리하고 있어요',
            textAlign: TextAlign.center, style: AppTypography.title),
        Gap.h8,
        const Text('잠시만 기다려주세요.', style: AppTypography.bodySecondary),
        Gap.h24,
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final item in BaselineDummy.analysisItems)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle_rounded,
                          size: 18, color: AppColors.primary),
                      const SizedBox(width: 8),
                      Text(item, style: AppTypography.body),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ErrorContent extends StatelessWidget {
  const _ErrorContent({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const MascotImage(pose: MascotPose.thinking, size: 150),
        Gap.h20,
        const Icon(Icons.error_outline_rounded, size: 32, color: AppColors.error),
        Gap.h12,
        const Text('측정 결과를 저장하지 못했어요',
            textAlign: TextAlign.center, style: AppTypography.title),
        Gap.h8,
        Text(message,
            textAlign: TextAlign.center, style: AppTypography.bodySecondary),
        Gap.h24,
        PrimaryButton(label: '다시 시도하기', onPressed: onRetry),
      ],
    );
  }
}
