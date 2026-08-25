import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/dummy_seed.dart';
import '../../../../features/records/application/recorded_days_provider.dart';
import '../../../../features/records/application/viewing_date_provider.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/card_section_header.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../application/diary_draft_provider.dart';
import '../../data/diary_providers.dart';
import '../../data/models/counsel_session.dart';
import '../../data/models/diary_entry.dart';
import '../../data/models/emotion_report.dart';

/// Screen 46 — 상담 후 감정 리포트·행동 가이드. Tabbed (감정 리포트 / 행동
/// 가이드). The re-viewable report for a written date. → 홈 작성일.
class ReportGuideScreen extends ConsumerStatefulWidget {
  const ReportGuideScreen({super.key});

  @override
  ConsumerState<ReportGuideScreen> createState() => _ReportGuideScreenState();
}

class _ReportGuideScreenState extends ConsumerState<ReportGuideScreen> {
  int _tab = 0;
  bool _saving = false;

  /// Saves the completed run (diary + report + counsel log) under the focused
  /// date, then returns to the written-day home.
  ///
  /// TODO(Phase 5): 요약/키워드/점수/리포트/상담 로그를 실제 AI 산출물로 대체 —
  /// 지금은 Step2에서 수정한 원문만 실데이터, 나머지는 샘플 콘텐츠.
  Future<void> _completeRecord() async {
    final writtenDate = ref.read(viewingDateProvider);
    final transcript =
        ref.read(diaryDraftProvider).transcript ?? DummySeed.diaryJan14.transcript;
    final sampleEntry = DummySeed.diaryJan14;
    final sampleReport = DummySeed.reportJan14;
    final now = DateTime.now();

    final entry = DiaryEntry(
      id: DateFormatter.dateKey(writtenDate),
      date: writtenDate,
      transcript: transcript,
      summary: sampleEntry.summary,
      emotionKeywords: sampleEntry.emotionKeywords,
      emotionIntensity: sampleEntry.emotionIntensity,
      emotionStability: sampleEntry.emotionStability,
      writtenAt: now,
    );
    final report = EmotionReport(
      date: writtenDate,
      emotionDistribution: sampleReport.emotionDistribution,
      emotionIntensity: sampleReport.emotionIntensity,
      recoveryPossibility: sampleReport.recoveryPossibility,
      analysisComment: sampleReport.analysisComment,
      behaviorGuides: sampleReport.behaviorGuides,
      recommendedActivities: sampleReport.recommendedActivities,
    );
    final counsel = CounselSession(
      date: writtenDate,
      startedAt: now.subtract(const Duration(minutes: 30)),
      endedAt: now,
      messages: DummySeed.counselJan14.messages,
    );

    setState(() => _saving = true);
    try {
      await ref
          .read(diaryRepositoryProvider)
          .saveRecord(entry: entry, report: report, counsel: counsel);
      ref.read(recordedDaysProvider.notifier).markRecorded(writtenDate);
      ref.read(diaryDraftProvider.notifier).clear();
      // 방금 저장한 날짜의 기록 화면들이 새 데이터를 읽도록 캐시 무효화.
      ref.invalidate(diaryEntryProvider(writtenDate));
      ref.invalidate(emotionReportProvider(writtenDate));
      ref.invalidate(counselSessionProvider(writtenDate));
      if (mounted) context.goNamed(AppRoute.homeWritten);
    } on AppException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final report = DummySeed.reportJan14;
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
                    child: Text('감정 리포트',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  IconButton(
                    icon: const Icon(Icons.help_outline_rounded, size: 20),
                    onPressed: () => showHelpSheet(
                      context,
                      title: '감정 리포트 도움말',
                      items: const [
                        '상담 내용을 바탕으로 만든 오늘의 감정 분석이에요.',
                        '행동 가이드 탭에서 실천할 수 있는 제안을 볼 수 있어요.',
                        '기록 완료하기를 누르면 이 날짜에 저장돼요.',
                      ],
                    ),
                  ),
                ],
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.sm, AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Row(
                        children: [
                          // TODO: 작은 차트를 들고 있는 포즈로 교체 예정
                          MascotImage(pose: MascotPose.heart, size: 84),
                          SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('오늘 상담을 통해\n나의 감정을 더 잘 이해했어요 💙',
                                    style: AppTypography.subtitle),
                                Gap.h8,
                                Text('상담 내용을 바탕으로 감정 상태와 행동 가이드를 정리했어요.',
                                    style: AppTypography.bodySecondary),
                              ],
                            ),
                          ),
                        ],
                      ),
                      Gap.h16,
                      _TabToggle(
                          index: _tab,
                          onChanged: (i) => setState(() => _tab = i)),
                      Gap.h16,
                      if (_tab == 0)
                        _ReportTab(report: report)
                      else
                        _GuideTab(report: report),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '기록 완료하기',
                  loading: _saving,
                  onPressed: _completeRecord,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TabToggle extends StatelessWidget {
  const _TabToggle({required this.index, required this.onChanged});
  final int index;
  final ValueChanged<int> onChanged;

  static const List<String> _labels = ['감정 리포트', '행동 가이드'];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.backgroundAlt,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Row(
        children: [
          for (var i = 0; i < _labels.length; i++)
            Expanded(
              child: GestureDetector(
                onTap: () => onChanged(i),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: index == i ? AppColors.primary : Colors.transparent,
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    _labels[i],
                    style: AppTypography.bodySecondary.copyWith(
                      color: index == i
                          ? AppColors.textOnPrimary
                          : AppColors.textSecondary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ReportTab extends StatelessWidget {
  const _ReportTab({required this.report});
  final EmotionReport report;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.pie_chart_outline_rounded, title: '오늘의 감정 요약'),
              Gap.h12,
              for (final e in report.emotionDistribution.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _EmotionRow(name: e.key, value: e.value),
                ),
              const Divider(color: AppColors.divider, height: 20),
              Row(
                children: [
                  Expanded(
                      child: _StatTile(
                          label: '감정 강도', value: report.emotionIntensity)),
                  Gap.w12,
                  Expanded(
                      child: _StatTile(
                          label: '회복 가능성', value: report.recoveryPossibility)),
                ],
              ),
            ],
          ),
        ),
        Gap.h12,
        const OddoCard(child: _ChangeChart()),
        Gap.h12,
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.auto_awesome_rounded, title: 'AI 분석 코멘트'),
              Gap.h8,
              Text(report.analysisComment, style: AppTypography.body),
            ],
          ),
        ),
      ],
    );
  }
}

class _GuideTab extends StatelessWidget {
  const _GuideTab({required this.report});
  final EmotionReport report;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.flag_outlined, title: '오늘의 행동 가이드'),
              Gap.h12,
              for (var i = 0; i < report.behaviorGuides.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _NumberedItem(
                      number: i + 1, text: report.behaviorGuides[i]),
                ),
            ],
          ),
        ),
        Gap.h12,
        OddoCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CardSectionHeader(
                  icon: Icons.spa_outlined, title: '추천 활동'),
              Gap.h12,
              for (final activity in report.recommendedActivities)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle_outline_rounded,
                          size: 18, color: AppColors.primary),
                      const SizedBox(width: 8),
                      Text(activity, style: AppTypography.body),
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

class _EmotionRow extends StatelessWidget {
  const _EmotionRow({required this.name, required this.value});
  final String name;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(width: 52, child: Text(name, style: AppTypography.bodySecondary)),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: LinearProgressIndicator(
              value: value,
              minHeight: 8,
              backgroundColor: AppColors.primarySoftBorder,
              valueColor: const AlwaysStoppedAnimation(AppColors.primary),
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 36,
          child: Text('${(value * 100).round()}%',
              textAlign: TextAlign.right,
              style: AppTypography.caption
                  .copyWith(fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value});
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AppTypography.caption),
          const SizedBox(height: 2),
          Text('$value',
              style: AppTypography.subtitle.copyWith(color: AppColors.primary)),
        ],
      ),
    );
  }
}

/// Simple 상담 전 → 중 → 후 mini bar chart (속상함 낮아짐).
class _ChangeChart extends StatelessWidget {
  const _ChangeChart();

  static const List<(String, double)> _points = [
    ('상담 전', 0.85),
    ('상담 중', 0.65),
    ('상담 후', 0.42),
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const CardSectionHeader(
            icon: Icons.show_chart_rounded, title: '감정 변화'),
        Gap.h16,
        SizedBox(
          height: 90,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              for (final p in _points)
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Container(
                        width: 28,
                        height: 70 * p.$2,
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius: BorderRadius.circular(6),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(p.$1, style: AppTypography.caption),
                    ],
                  ),
                ),
            ],
          ),
        ),
        Gap.h8,
        const Text('상담을 지나며 속상함이 조금씩 가라앉았어요.',
            style: AppTypography.caption),
      ],
    );
  }
}

class _NumberedItem extends StatelessWidget {
  const _NumberedItem({required this.number, required this.text});
  final int number;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: const BoxDecoration(
              color: AppColors.primary, shape: BoxShape.circle),
          alignment: Alignment.center,
          child: Text('$number',
              style: AppTypography.caption.copyWith(
                  color: AppColors.textOnPrimary, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 10),
        Expanded(child: Text(text, style: AppTypography.body)),
      ],
    );
  }
}
