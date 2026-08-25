import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_assets.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/records_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../diary/data/diary_providers.dart';
import '../../application/viewing_date_provider.dart';
import '../widgets/record_async_view.dart';
import '../widgets/record_top_bar.dart';

/// Screen 48 — 일기 상세 (일기 tab of the written-day context). Shows the
/// viewed date's saved diary from Firestore.
class DiaryDetailScreen extends ConsumerWidget {
  const DiaryDetailScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final date = ref.watch(viewingDateProvider);
    final entryAsync = ref.watch(diaryEntryProvider(date));

    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          const RecordTopBar(title: '일기 상세'),
          Expanded(
            child: RecordAsyncView(
              value: entryAsync,
              emptyMessage: '이 날짜에는 아직 일기가 없어요',
              builder: (entry) => SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ClipRRect(
                      borderRadius: AppRadius.card,
                      child: AspectRatio(
                        aspectRatio: 16 / 10,
                        child: Container(
                          color: AppColors.primarySoft,
                          alignment: Alignment.center,
                          // TODO: 노을 지는 창가에서 일기 쓰는 장면으로 교체 예정
                          child: const MascotImage(
                              pose: MascotPose.writing, size: 130),
                        ),
                      ),
                    ),
                    Gap.h16,
                    Row(
                      children: [
                        Text(RecordsDummy.diaryDateLabel(date),
                            style: AppTypography.title
                                .copyWith(color: AppColors.primary)),
                        const Spacer(),
                        _MoodChip(entry.emotionKeywords.isNotEmpty
                            ? entry.emotionKeywords.first
                            : RecordsDummy.diaryMood),
                      ],
                    ),
                    Gap.h4,
                    Text(
                      entry.writtenAt != null
                          ? '${DateFormatter.fullKoreanDate(date)} · ${DateFormatter.hhmm(entry.writtenAt!)} 작성'
                          : DateFormatter.fullKoreanDate(date),
                      style: AppTypography.caption,
                    ),
                    Gap.h16,
                    Text(entry.transcript,
                        style: AppTypography.body.copyWith(height: 1.7)),
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

class _MoodChip extends StatelessWidget {
  const _MoodChip(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(label,
          style: AppTypography.caption.copyWith(
              color: AppColors.primary, fontWeight: FontWeight.w700)),
    );
  }
}
