import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../application/step1_analysis_controller.dart';

/// Screen 38 — Step 1 처리 중. 녹음/얼굴 캡처를 baseline과 비교해 감정을
/// 뽑는 실제 서버 호출(step1AnalysisController)을 진행하고, 끝나면 Step 2
/// 확인하기로 넘어간다. 실패하면 재시도할 수 있다.
class DiaryStep1ProcessingScreen extends ConsumerStatefulWidget {
  const DiaryStep1ProcessingScreen({super.key});

  @override
  ConsumerState<DiaryStep1ProcessingScreen> createState() =>
      _DiaryStep1ProcessingScreenState();
}

class _DiaryStep1ProcessingScreenState
    extends ConsumerState<DiaryStep1ProcessingScreen> {
  static const List<String> _items = ['음성 변환', '핵심 내용 분석', '감정 분석 중'];

  @override
  void initState() {
    super.initState();
    // initState 안에서 바로 submit()을 부르면 상태 변경이 빌드 도중 일어날 수
    // 있어 다음 마이크로태스크로 미룬다(baseline_analyzing_screen과 동일).
    Future.microtask(
      () => ref.read(step1AnalysisControllerProvider.notifier).submit(),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(step1AnalysisControllerProvider, (previous, next) {
      final result = next.value;
      if (result != null && mounted) {
        context.pushReplacementNamed(AppRoute.diaryStep2Confirm);
      }
    });

    final analysis = ref.watch(step1AnalysisControllerProvider);

    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(
                      Icons.arrow_back_ios_new_rounded,
                      size: 20,
                    ),
                    onPressed: () {
                      if (context.canPop()) context.pop();
                    },
                  ),
                  const Expanded(
                    child: Text(
                      'Step 1. 말하기',
                      textAlign: TextAlign.center,
                      style: AppTypography.subtitle,
                    ),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH,
                    ),
                    child: analysis.hasError
                        ? _ErrorContent(
                            message: _errorMessage(analysis.error),
                            onRetry: () => ref
                                .read(step1AnalysisControllerProvider.notifier)
                                .submit(),
                          )
                        : const _LoadingContent(items: _items),
                  ),
                ),
              ),
            ],
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
  const _LoadingContent({required this.items});
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Center(
          child: SizedBox(
            width: 30,
            height: 30,
            child: CircularProgressIndicator(
              strokeWidth: 3,
              color: AppColors.primary,
            ),
          ),
        ),
        Gap.h20,
        const Text(
          '처리 중이에요',
          textAlign: TextAlign.center,
          style: AppTypography.title,
        ),
        Gap.h8,
        const Text(
          '말씀해 주신 내용을 텍스트로 바꾸고\n감정을 확인하고 있어요.',
          textAlign: TextAlign.center,
          style: AppTypography.bodySecondary,
        ),
        Gap.h24,
        // TODO: 헤드폰 끼고 노트북을 보는 포즈로 교체 예정
        const Center(child: MascotImage(pose: MascotPose.thinking, size: 150)),
        Gap.h24,
        _ProgressCard(items: items),
        Gap.h16,
        Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: AppColors.primarySoft,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          child: const Row(
            children: [
              Icon(
                Icons.lightbulb_outline_rounded,
                size: 16,
                color: AppColors.primary,
              ),
              SizedBox(width: 6),
              Expanded(
                child: Text(
                  '잠시만 기다려 주세요! 보통 10~20초 정도 소요돼요.',
                  style: AppTypography.caption,
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
        const Icon(
          Icons.error_outline_rounded,
          size: 32,
          color: AppColors.error,
        ),
        Gap.h12,
        const Text(
          '감정 분석을 완료하지 못했어요',
          textAlign: TextAlign.center,
          style: AppTypography.title,
        ),
        Gap.h8,
        Text(
          message,
          textAlign: TextAlign.center,
          style: AppTypography.bodySecondary,
        ),
        Gap.h24,
        PrimaryButton(label: '다시 시도하기', onPressed: onRetry),
      ],
    );
  }
}

class _ProgressCard extends StatelessWidget {
  const _ProgressCard({required this.items});
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '분석 진행 상황',
                style: AppTypography.bodySecondary.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              Text(
                '70%',
                style: AppTypography.bodySecondary.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          Gap.h8,
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: const LinearProgressIndicator(
              value: 0.7,
              minHeight: 8,
              backgroundColor: AppColors.primarySoftBorder,
              valueColor: AlwaysStoppedAnimation(AppColors.primary),
            ),
          ),
          Gap.h12,
          for (final item in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  const Icon(
                    Icons.check_circle_rounded,
                    size: 16,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 8),
                  Text(item, style: AppTypography.bodySecondary),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
