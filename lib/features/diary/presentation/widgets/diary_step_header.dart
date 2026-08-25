import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/step_indicator.dart';

/// Shared header for the 4-step diary-write flow: a top row (back/close +
/// title + help) and the [StepIndicator] showing the active step.
class DiaryStepHeader extends StatelessWidget {
  const DiaryStepHeader({
    super.key,
    this.title = '일기 작성하기',
    required this.currentStep,
    this.showHelp = true,
    this.leadingClose = false,
  });

  final String title;
  final int currentStep; // 0=말하기 .. 3=상담하기
  final bool showHelp;
  final bool leadingClose;

  static const List<String> steps = ['말하기', '확인하기', '영상 제작', '상담하기'];

  /// 단계별 도움말 문구.
  static const List<List<String>> _helpByStep = [
    [
      '탄카츄와 통화하듯 오늘 하루를 편하게 이야기해요.',
      '말한 내용은 자동으로 텍스트로 변환돼요.',
      '중간에 멈춰도 괜찮아요. 통화 종료를 누르면 다음 단계로 가요.',
    ],
    [
      'AI가 정리한 대화 원문과 요약을 확인하는 단계예요.',
      '틀린 부분은 원문을 직접 수정할 수 있어요.',
      '내용이 부족하면 "추가 정보가 필요해요!"로 더 이야기할 수 있어요.',
    ],
    [
      '오늘의 이야기를 짧은 영상으로 만들어드려요.',
      '완성된 영상은 플레이어를 눌러 다시 볼 수 있어요.',
      '영상은 이 날짜의 기록에 함께 저장돼요.',
    ],
    [
      '탄카츄와 영상 상담으로 오늘의 감정을 돌아봐요.',
      '상담을 마치면 감정 리포트와 행동 가이드가 만들어져요.',
      '상담 내용은 상담 기록 탭에서 다시 볼 수 있어요.',
    ],
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            IconButton(
              icon: Icon(
                  leadingClose
                      ? Icons.close_rounded
                      : Icons.arrow_back_ios_new_rounded,
                  size: 20),
              onPressed: () {
                if (context.canPop()) context.pop();
              },
            ),
            Expanded(
              child: Text(title,
                  textAlign: TextAlign.center, style: AppTypography.subtitle),
            ),
            if (showHelp)
              IconButton(
                icon: const Icon(Icons.help_outline_rounded, size: 20),
                onPressed: () => showHelpSheet(
                  context,
                  title: 'Step ${currentStep + 1}. ${steps[currentStep]} 도움말',
                  items: _helpByStep[currentStep],
                ),
              )
            else
              const SizedBox(width: 48),
          ],
        ),
        Padding(
          padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.screenH, vertical: AppSpacing.xs),
          child: StepIndicator(steps: steps, currentIndex: currentStep),
        ),
      ],
    );
  }
}
