import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../data/dummy/records_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../diary/data/diary_providers.dart';
import '../../../diary/data/models/emotion_report.dart';
import '../../application/viewing_date_provider.dart';
import '../widgets/record_async_view.dart';
import '../widgets/record_top_bar.dart';

/// Screen 49 — 감정 리포트 (리포트 tab of the written-day context). Shows the
/// viewed date's saved report from Firestore.
/// (지표 타일/추이 스파크라인은 아직 샘플 — Phase 5에서 실측값으로 교체.)
class EmotionReportScreen extends ConsumerWidget {
  const EmotionReportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final date = ref.watch(viewingDateProvider);
    final reportAsync = ref.watch(emotionReportProvider(date));

    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          const RecordTopBar(title: '감정 리포트'),
          Expanded(
            child: RecordAsyncView(
              value: reportAsync,
              emptyMessage: '이 날짜에는 아직 감정 리포트가 없어요',
              builder: (report) => SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(RecordsDummy.reportTitle(date),
                        style: AppTypography.title),
                    Gap.h4,
                    Text(RecordsDummy.reportPeriod(date),
                        style: AppTypography.caption),
                    Gap.h16,
                    _SummaryCard(report: report),
                    Gap.h12,
                    Row(
                      children: [
                        for (var i = 0;
                            i < RecordsDummy.reportMetrics.length;
                            i++) ...[
                          if (i > 0) const SizedBox(width: 8),
                          Expanded(
                              child:
                                  _MetricTile(RecordsDummy.reportMetrics[i])),
                        ],
                      ],
                    ),
                    Gap.h12,
                    OddoCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const CardSectionHeader(
                              icon: Icons.auto_awesome_rounded,
                              title: '분석 코멘트'),
                          Gap.h8,
                          Text(report.analysisComment,
                              style: AppTypography.body),
                        ],
                      ),
                    ),
                    Gap.h12,
                    _ListCard(
                      icon: Icons.spa_outlined,
                      title: '추천 활동',
                      items: report.recommendedActivities,
                    ),
                    Gap.h12,
                    _ListCard(
                      icon: Icons.tips_and_updates_outlined,
                      title: '맞춤 권고 사항',
                      items: report.behaviorGuides,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.report});
  final EmotionReport report;

  @override
  Widget build(BuildContext context) {
    // 대표 감정 = 분포에서 비중이 가장 큰 항목.
    final top = report.emotionDistribution.entries
        .reduce((a, b) => a.value >= b.value ? a : b);

    return OddoCard(
      child: Row(
        children: [
          Column(
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: const BoxDecoration(
                    color: AppColors.primarySoft, shape: BoxShape.circle),
                child: const Icon(Icons.sentiment_satisfied_alt_rounded,
                    size: 32, color: AppColors.primary),
              ),
              Gap.h8,
              Text(top.key,
                  style: AppTypography.bodySecondary
                      .copyWith(fontWeight: FontWeight.w700)),
              Text('${(top.value * 100).round()}%',
                  style:
                      AppTypography.title.copyWith(color: AppColors.primary)),
            ],
          ),
          const SizedBox(width: AppSpacing.lg),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('감정 변화 추이', style: AppTypography.caption),
                Gap.h8,
                _Sparkline(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Sparkline extends StatelessWidget {
  const _Sparkline();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (final v in RecordsDummy.reportTrend)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Container(
                  height: 8 + 48 * v,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.35 + 0.5 * v),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile(this.metric);
  final RecordMetric metric;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.card,
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          Icon(metric.icon, size: 20, color: metric.color),
          const SizedBox(height: 6),
          Text(metric.value,
              style: AppTypography.bodySecondary
                  .copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(metric.label,
              textAlign: TextAlign.center, style: AppTypography.caption),
        ],
      ),
    );
  }
}

class _ListCard extends StatelessWidget {
  const _ListCard(
      {required this.icon, required this.title, required this.items});
  final IconData icon;
  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CardSectionHeader(icon: icon, title: title),
          Gap.h12,
          for (final item in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_outline_rounded,
                      size: 18, color: AppColors.primary),
                  const SizedBox(width: 8),
                  Expanded(child: Text(item, style: AppTypography.body)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
