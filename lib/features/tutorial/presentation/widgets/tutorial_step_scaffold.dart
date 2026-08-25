import 'package:flutter/material.dart';

import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/primary_button.dart';
import 'tutorial_header.dart';

/// Common layout for a light tutorial step (10, 12–15):
/// [TutorialHeader] + big headline/subtitle + a list of content cards +
/// a bottom primary CTA. Body items are auto-spaced.
class TutorialStepScaffold extends StatelessWidget {
  const TutorialStepScaffold({
    super.key,
    required this.appBarTitle,
    required this.current,
    this.stepLabel,
    this.stepLabelIcon,
    this.leadingClose = false,
    this.showHelp = true,
    required this.headline,
    this.subtitle,
    required this.body,
    required this.primaryLabel,
    this.primaryIcon,
    required this.onPrimary,
  });

  final String appBarTitle;
  final int current;
  final String? stepLabel;
  final IconData? stepLabelIcon;
  final bool leadingClose;
  final bool showHelp;
  final String headline;
  final String? subtitle;
  final List<Widget> body;
  final String primaryLabel;
  final IconData? primaryIcon;
  final VoidCallback onPrimary;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: TutorialHeader(
                  title: appBarTitle,
                  current: current,
                  stepLabel: stepLabel,
                  stepLabelIcon: stepLabelIcon,
                  leading: leadingClose
                      ? Icons.close_rounded
                      : Icons.arrow_back_ios_new_rounded,
                  showHelp: showHelp,
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.md, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(headline, style: AppTypography.display),
                      if (subtitle != null) ...[
                        const SizedBox(height: AppSpacing.xs),
                        Text(subtitle!, style: AppTypography.bodySecondary),
                      ],
                      const SizedBox(height: AppSpacing.lg),
                      for (var i = 0; i < body.length; i++) ...[
                        if (i > 0) const SizedBox(height: AppSpacing.md),
                        body[i],
                      ],
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: primaryLabel,
                  leadingIcon: primaryIcon,
                  onPressed: onPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
