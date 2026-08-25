import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';

/// Screen 45 — 상담 후 리포트 생성. Loading page shown right after the counsel
/// call ends; auto-advances to the finished report after a dummy delay
/// (tap to skip).
class ReportGeneratingScreen extends StatefulWidget {
  const ReportGeneratingScreen({super.key});

  @override
  State<ReportGeneratingScreen> createState() => _ReportGeneratingScreenState();
}

class _ReportGeneratingScreenState extends State<ReportGeneratingScreen> {
  Timer? _timer;
  bool _advanced = false;

  static const List<String> _items = ['상담 내용 정리', '감정 분석', '맞춤 가이드 생성'];

  @override
  void initState() {
    super.initState();
    _timer = Timer(const Duration(seconds: 3), _advance);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _advance() {
    if (_advanced || !mounted) return;
    _advanced = true;
    context.pushReplacementNamed(AppRoute.reportGuide);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
                    onPressed: () {
                      if (context.canPop()) context.pop();
                    },
                  ),
                  const Expanded(
                    child: Text('상담 후 리포트 생성',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.screenH),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Center(
                          child: SizedBox(
                            width: 30,
                            height: 30,
                            child: CircularProgressIndicator(
                                strokeWidth: 3, color: AppColors.primary),
                          ),
                        ),
                        Gap.h20,
                        const Text('리포트를 만들고 있어요',
                            textAlign: TextAlign.center,
                            style: AppTypography.title),
                        Gap.h8,
                        const Text('상담 내용을 바탕으로\n나만의 맞춤 리포트를 만들고 있어요.',
                            textAlign: TextAlign.center,
                            style: AppTypography.bodySecondary),
                        Gap.h24,
                        // TODO: 차트를 정리하는 포즈로 교체 예정
                        const Center(
                            child: MascotImage(
                                pose: MascotPose.clipboard, size: 150)),
                        Gap.h24,
                        const _ProgressCard(items: _items),
                        Gap.h16,
                        Container(
                          padding: const EdgeInsets.all(AppSpacing.sm),
                          decoration: BoxDecoration(
                            color: AppColors.primarySoft,
                            borderRadius: BorderRadius.circular(AppRadius.sm),
                          ),
                          child: const Row(
                            children: [
                              Icon(Icons.lightbulb_outline_rounded,
                                  size: 16, color: AppColors.primary),
                              SizedBox(width: 6),
                              Expanded(
                                child: Text('잠시만 기다려 주세요! 보통 10~20초 정도 소요돼요.',
                                    style: AppTypography.caption),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: _StatusButton(onTap: _advance),
              ),
            ],
          ),
        ),
      ),
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
              Text('리포트 생성 상황',
                  style: AppTypography.bodySecondary
                      .copyWith(fontWeight: FontWeight.w700)),
              const Spacer(),
              Text('70%',
                  style: AppTypography.bodySecondary.copyWith(
                      color: AppColors.primary, fontWeight: FontWeight.w700)),
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
                  const Icon(Icons.check_circle_rounded,
                      size: 16, color: AppColors.primary),
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

class _StatusButton extends StatelessWidget {
  const _StatusButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.backgroundAlt,
      borderRadius: AppRadius.button,
      child: InkWell(
        borderRadius: AppRadius.button,
        onTap: onTap,
        child: Container(
          height: 56,
          alignment: Alignment.center,
          child: Text('리포트 보기 (잠시 후 자동으로 이동해요)',
              style: AppTypography.button
                  .copyWith(color: AppColors.textSecondary)),
        ),
      ),
    );
  }
}
