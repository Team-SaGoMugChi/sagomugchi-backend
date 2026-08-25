import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/help_sheet.dart';

/// Shared tutorial top bar: leading (close/back) + centered title + help, then
/// a 5-dot step progress and an optional sub-step label. Light + dark variants.
class TutorialHeader extends StatelessWidget {
  const TutorialHeader({
    super.key,
    required this.title,
    required this.current,
    this.total = 5,
    this.stepLabel,
    this.stepLabelIcon,
    this.leading,
    this.onLeading,
    this.showHelp = true,
    this.dark = false,
  });

  final String title;
  final int current; // 0-based
  final int total;
  final String? stepLabel;
  final IconData? stepLabelIcon;
  final IconData? leading;
  final VoidCallback? onLeading;
  final bool showHelp;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final fg = dark ? AppColors.callTextPrimary : AppColors.textStrong;
    return Column(
      children: [
        Row(
          children: [
            if (leading != null)
              IconButton(
                icon: Icon(leading, size: 20, color: fg),
                onPressed: onLeading ??
                    () {
                      if (context.canPop()) context.pop();
                    },
              )
            else
              const SizedBox(width: 48),
            Expanded(
              child: Text(
                title,
                textAlign: TextAlign.center,
                style: AppTypography.bodyLarge
                    .copyWith(color: fg, fontWeight: FontWeight.w600),
              ),
            ),
            if (showHelp)
              IconButton(
                icon: Icon(Icons.help_outline_rounded, size: 20, color: fg),
                onPressed: () => showHelpSheet(
                  context,
                  title: '튜토리얼 도움말',
                  items: const [
                    'Oddo 사용법을 5단계로 짧게 알려드려요.',
                    '각 단계의 "다음" 버튼으로 순서대로 진행돼요.',
                    '연습 통화에서는 실제 기록이 저장되지 않으니 편하게 해보세요.',
                  ],
                ),
              )
            else
              const SizedBox(width: 48),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
          child: _DotStepper(total: total, current: current, dark: dark),
        ),
        if (stepLabel != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (stepLabelIcon != null) ...[
                Icon(stepLabelIcon, size: 14, color: AppColors.primary),
                const SizedBox(width: 4),
              ],
              Text(
                stepLabel!,
                style: AppTypography.caption.copyWith(
                    color: AppColors.primary, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

class _DotStepper extends StatelessWidget {
  const _DotStepper({required this.total, required this.current, this.dark = false});

  final int total;
  final int current;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final inactive =
        dark ? AppColors.callSurface : AppColors.primarySoftBorder;
    return Row(
      children: [
        for (var i = 0; i < total; i++) ...[
          if (i > 0)
            Expanded(
              child: Container(
                height: 3,
                color: i <= current ? AppColors.primary : inactive,
              ),
            ),
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i <= current ? AppColors.primary : inactive,
            ),
          ),
        ],
      ],
    );
  }
}
