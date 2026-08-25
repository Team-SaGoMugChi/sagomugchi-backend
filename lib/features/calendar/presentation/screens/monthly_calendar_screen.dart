import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/calendar_dummy.dart';
import '../../../../features/home/presentation/widgets/diary_start_modal.dart';
import '../../../../features/records/application/recorded_days_provider.dart';
import '../../../../features/records/application/viewing_date_provider.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../widgets/monthly_calendar.dart';

/// Screens 33/34 — 월간 캘린더·날짜 선택. One calendar; the bottom card +
/// CTA switch by whether the selected day has a record.
class MonthlyCalendarScreen extends ConsumerStatefulWidget {
  const MonthlyCalendarScreen({super.key});

  @override
  ConsumerState<MonthlyCalendarScreen> createState() =>
      _MonthlyCalendarScreenState();
}

class _MonthlyCalendarScreenState extends ConsumerState<MonthlyCalendarScreen> {
  DateTime _month = CalendarDummy.month;
  DateTime _selected = CalendarDummy.today;

  @override
  Widget build(BuildContext context) {
    final recorded = ref.watch(recordedDaysProvider);
    final isWritten = recorded
        .contains(DateTime(_selected.year, _selected.month, _selected.day));
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
                    child: Text('날짜 선택',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  IconButton(
                    icon: const Icon(Icons.help_outline_rounded, size: 20),
                    onPressed: () => showHelpSheet(
                      context,
                      title: '날짜 선택 도움말',
                      items: const [
                        '보라색 배경 날짜는 일기가 작성된 날이에요.',
                        '날짜를 고르면 아래 카드에서 상태를 확인할 수 있어요.',
                        '지난 날짜를 골라 그날의 일기를 새로 쓸 수도 있어요.',
                      ],
                    ),
                  ),
                ],
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH, 0,
                      AppSpacing.screenH, AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                                '캘린더에서 원하는 날짜를 선택해 주세요.\n작성한 날짜는 파란 배경으로 표시돼요.',
                                style: AppTypography.bodySecondary),
                          ),
                          // TODO: 캘린더를 안내하는 정면 포즈로 교체 예정
                          MascotImage(pose: MascotPose.front, size: 72),
                        ],
                      ),
                      Gap.h16,
                      MonthlyCalendar(
                        month: _month,
                        today: CalendarDummy.today,
                        selected: _selected,
                        recordedDays: recorded,
                        onSelect: (d) => setState(() => _selected = d),
                        onPrevMonth: () => setState(() =>
                            _month = DateTime(_month.year, _month.month - 1)),
                        onNextMonth: () => setState(() =>
                            _month = DateTime(_month.year, _month.month + 1)),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: Column(
                  // 카드가 항상 하단 버튼과 같은 전체 폭을 갖도록 stretch.
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _SelectCard(date: _selected, isWritten: isWritten),
                    Gap.h12,
                    isWritten
                        ? PrimaryButton(
                            label: '이 날짜 보기',
                            onPressed: () {
                              ref
                                  .read(viewingDateProvider.notifier)
                                  .set(_selected);
                              context.goNamed(AppRoute.homeWritten);
                            },
                          )
                        : PrimaryButton(
                            label: '이 날짜에 일기 작성하기',
                            onPressed: () =>
                                showDiaryStartModal(context, ref, date: _selected),
                          ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 작성일/미작성일이 같은 골격(날짜 → 상태 배지 → 안내 한 줄)을 공유하고,
/// 상태는 배지의 색과 문구로만 표현한다 (개선안 B).
class _SelectCard extends StatelessWidget {
  const _SelectCard({required this.date, required this.isWritten});

  final DateTime date;
  final bool isWritten;

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      // 두 상태가 항상 같은 높이를 갖도록 각 줄을 고정 높이로 구성한다
      // (날짜 1줄 + 배지 + 안내 1줄, 줄바꿈 없음).
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(DateFormatter.fullKoreanDate(date),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.body.copyWith(fontWeight: FontWeight.w700)),
          Gap.h8,
          _StatusBadge(isWritten: isWritten),
          Gap.h8,
          Text(
            isWritten ? '일기 · 리포트 · 상담 기록이 저장되어 있어요' : '이 날의 감정을 기록해보세요',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.caption,
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.isWritten});
  final bool isWritten;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: isWritten ? AppColors.primary : AppColors.backgroundAlt,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        // 두 상태 모두 1px 테두리를 차지해 배지 높이가 항상 같도록,
        // 작성일은 투명 테두리를 쓴다.
        border: Border.all(
            color: isWritten ? Colors.transparent : AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isWritten
                ? Icons.check_rounded
                : Icons.radio_button_unchecked_rounded,
            size: 14,
            color:
                isWritten ? AppColors.textOnPrimary : AppColors.textSecondary,
          ),
          const SizedBox(width: 5),
          Text(
            isWritten ? '기록 완료' : '기록 없음',
            style: AppTypography.caption.copyWith(
              color: isWritten
                  ? AppColors.textOnPrimary
                  : AppColors.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
