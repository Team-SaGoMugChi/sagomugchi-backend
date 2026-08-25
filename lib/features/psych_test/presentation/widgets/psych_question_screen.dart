import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/psych_test_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/step_progress_bar.dart';

/// How the answer options are laid out.
enum PsychOptionLayout {
  /// 5-point list, radio on the left (Big 5).
  likert,

  /// Two large illustrated cards (MBTI).
  duo,

  /// List with a small illustration on the left + radio on the right (성향).
  illustrated,
}

/// Shared question screen for all three tests (24/25/26). The 3 screens only
/// pass different data + a [layout]; selection state lives here.
class PsychQuestionScreen extends StatefulWidget {
  const PsychQuestionScreen({
    super.key,
    required this.testTitle,
    required this.journeyIndex,
    required this.questionNumber,
    required this.totalQuestions,
    required this.question,
    required this.layout,
    required this.onNext,
    required this.hint,
    this.mascotPose = MascotPose.front,
  });

  final String testTitle;
  final int journeyIndex; // index in PsychTestDummy.journeySteps
  final int questionNumber;
  final int totalQuestions;
  final PsychQuestion question;
  final PsychOptionLayout layout;
  final VoidCallback onNext;
  final String hint;
  final MascotPose mascotPose;

  @override
  State<PsychQuestionScreen> createState() => _PsychQuestionScreenState();
}

class _PsychQuestionScreenState extends State<PsychQuestionScreen> {
  int? _selected;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              _Header(title: widget.testTitle),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                child: StepProgressBar(
                  labels: PsychTestDummy.journeySteps,
                  currentIndex: widget.journeyIndex,
                ),
              ),
              Gap.h16,
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.screenH),
                child: _QuestionProgress(
                  number: widget.questionNumber,
                  total: widget.totalQuestions,
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(widget.question.text,
                                style: AppTypography.title),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          // TODO: 검사별 어울리는 포즈로 교체 예정 (call site 지정)
                          MascotImage(pose: widget.mascotPose, size: 72),
                        ],
                      ),
                      Gap.h20,
                      ..._buildOptions(),
                      Gap.h12,
                      _HintRow(text: widget.hint),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '다음',
                  trailingIcon: Icons.chevron_right_rounded,
                  onPressed: widget.onNext,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildOptions() {
    final options = widget.question.options;
    switch (widget.layout) {
      case PsychOptionLayout.likert:
        return [
          for (var i = 0; i < options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _LikertOption(
                text: options[i].text,
                selected: _selected == i,
                onTap: () => setState(() => _selected = i),
              ),
            ),
        ];
      case PsychOptionLayout.duo:
        return [
          for (var i = 0; i < options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _DuoOption(
                option: options[i],
                selected: _selected == i,
                onTap: () => setState(() => _selected = i),
              ),
            ),
        ];
      case PsychOptionLayout.illustrated:
        return [
          for (var i = 0; i < options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _IllustratedOption(
                option: options[i],
                selected: _selected == i,
                onTap: () => setState(() => _selected = i),
              ),
            ),
        ];
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: () {
            if (context.canPop()) context.pop();
          },
        ),
        Expanded(
          child: Text(title,
              textAlign: TextAlign.center,
              style: AppTypography.bodyLarge
                  .copyWith(fontWeight: FontWeight.w600)),
        ),
        IconButton(
          icon: const Icon(Icons.help_outline_rounded, size: 20),
          onPressed: () => showHelpSheet(
            context,
            title: '심리테스트 도움말',
            items: const [
              '정답은 없어요. 평소의 나와 가장 가까운 쪽을 골라주세요.',
              '결과는 챗봇 페르소나와 상담 맞춤화에 사용돼요.',
              '중간에 나가도 이어하기로 다시 진행할 수 있어요.',
            ],
          ),
        ),
      ],
    );
  }
}

class _QuestionProgress extends StatelessWidget {
  const _QuestionProgress({required this.number, required this.total});
  final int number;
  final int total;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: LinearProgressIndicator(
            value: total == 0 ? 0 : number / total,
            minHeight: 6,
            backgroundColor: AppColors.primarySoftBorder,
            valueColor: const AlwaysStoppedAnimation(AppColors.primary),
          ),
        ),
        const SizedBox(height: 6),
        Text('Q$number / $total',
            style: AppTypography.caption
                .copyWith(color: AppColors.primary, fontWeight: FontWeight.w700)),
      ],
    );
  }
}

class _OptionRadio extends StatelessWidget {
  const _OptionRadio({required this.selected});
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 22,
      height: 22,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: selected ? AppColors.primary : Colors.transparent,
        border: Border.all(
          color: selected ? AppColors.primary : AppColors.border,
          width: 2,
        ),
      ),
      child: selected
          ? const Icon(Icons.circle, size: 8, color: AppColors.textOnPrimary)
          : null,
    );
  }
}

/// Shared selected/unselected card decoration.
BoxDecoration _optionDecoration(bool selected) {
  return BoxDecoration(
    color: selected ? AppColors.primarySoft : AppColors.surface,
    borderRadius: AppRadius.button,
    border: Border.all(
      color: selected ? AppColors.primary : AppColors.border,
      width: selected ? 1.5 : 1,
    ),
  );
}

class _LikertOption extends StatelessWidget {
  const _LikertOption(
      {required this.text, required this.selected, required this.onTap});
  final String text;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        decoration: _optionDecoration(selected),
        child: Row(
          children: [
            _OptionRadio(selected: selected),
            const SizedBox(width: 12),
            Text(text,
                style: AppTypography.body.copyWith(
                    color: selected ? AppColors.primary : AppColors.textPrimary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400)),
          ],
        ),
      ),
    );
  }
}

class _DuoOption extends StatelessWidget {
  const _DuoOption(
      {required this.option, required this.selected, required this.onTap});
  final PsychOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: _optionDecoration(selected),
        clipBehavior: Clip.antiAlias,
        child: Column(
          children: [
            SizedBox(
              height: 120,
              width: double.infinity,
              child: Stack(
                children: [
                  Container(
                    color: AppColors.primarySoft,
                    alignment: Alignment.center,
                    // TODO: 실제 일러스트로 교체 예정
                    child: Icon(option.illustration ?? Icons.image_outlined,
                        size: 48, color: AppColors.primary),
                  ),
                  Positioned(
                      top: 10, left: 10, child: _OptionRadio(selected: selected)),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Text(
                option.text,
                textAlign: TextAlign.center,
                style: AppTypography.body.copyWith(
                    color: selected ? AppColors.primary : AppColors.textStrong,
                    fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _IllustratedOption extends StatelessWidget {
  const _IllustratedOption(
      {required this.option, required this.selected, required this.onTap});
  final PsychOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: _optionDecoration(selected),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: const BoxDecoration(
                color: AppColors.primarySoft,
                shape: BoxShape.circle,
              ),
              // TODO: 실제 일러스트로 교체 예정
              child: Icon(option.illustration ?? Icons.image_outlined,
                  size: 22, color: AppColors.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(option.text,
                  style: AppTypography.body.copyWith(
                      color: selected ? AppColors.primary : AppColors.textPrimary,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400)),
            ),
            const SizedBox(width: 8),
            _OptionRadio(selected: selected),
          ],
        ),
      ),
    );
  }
}

class _HintRow extends StatelessWidget {
  const _HintRow({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.lightbulb_outline_rounded,
              size: 16, color: AppColors.primary),
          const SizedBox(width: 6),
          Expanded(child: Text(text, style: AppTypography.caption)),
        ],
      ),
    );
  }
}
