import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../features/onboarding/application/onboarding_controller.dart';
import '../../../../features/records/application/recorded_days_provider.dart';
import '../../../../features/records/application/viewing_date_provider.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_app_bar.dart';
import '../../../../widgets/oddo_card.dart';

/// 한 줄 알림 항목 (실데이터에서 파생 생성).
class _NotifItem {
  const _NotifItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.timeLabel,
    this.unread = false,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String timeLabel;
  final bool unread;
  final VoidCallback? onTap;
}

/// Auxiliary — 알림. 푸시 인프라 없이 내 실제 기록 상태에서 알림 피드를
/// 파생 생성한다 (항상 현재 상태와 일치). Phase 7에서 로컬 푸시가 생기면
/// "발송된 알림" 항목이 이 리스트에 합류하는 구조.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  static DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

  String _relativeLabel(DateTime date, DateTime today) {
    final diff = today.difference(date).inDays;
    if (diff <= 0) return '오늘';
    if (diff == 1) return '어제';
    if (diff < 7) return '$diff일 전';
    return DateFormatter.monthDay(date);
  }

  List<_NotifItem> _buildItems(BuildContext context, WidgetRef ref) {
    final today = _dateOnly(DateTime.now());
    final recorded = ref.watch(recordedDaysProvider);
    final onboarded = ref.watch(onboardingCompleteProvider);
    final items = <_NotifItem>[];

    void goToDate(DateTime date, {required bool written}) {
      ref.read(viewingDateProvider.notifier).set(date);
      context.goNamed(written ? AppRoute.homeWritten : AppRoute.home);
    }

    // ① 온보딩 미완료 안내.
    if (!onboarded) {
      items.add(_NotifItem(
        icon: Icons.favorite_rounded,
        title: '첫 감정 측정을 완료해보세요',
        subtitle: '얼굴·음성 기준 데이터가 있어야 감정 분석이 정확해져요',
        timeLabel: '오늘',
        unread: true,
        onTap: () => context.goNamed(AppRoute.home),
      ));
    }

    // ② 오늘 일기 미작성 리마인더.
    if (!recorded.contains(today)) {
      items.add(_NotifItem(
        icon: Icons.edit_note_rounded,
        title: '오늘의 감정을 아직 기록하지 않았어요',
        subtitle: '탄카츄가 기다리고 있어요 · 탭해서 작성하기',
        timeLabel: '오늘',
        unread: true,
        onTap: () => goToDate(today, written: false),
      ));
    }

    // ③ 이번 주(월~일) 기록 요약.
    final weekStart = today.subtract(Duration(days: today.weekday - 1));
    final weekCount = recorded
        .where((d) => !d.isBefore(weekStart) && !d.isAfter(today))
        .length;
    if (weekCount > 0) {
      items.add(_NotifItem(
        icon: Icons.insights_rounded,
        title: '이번 주 $weekCount일 기록했어요',
        subtitle: '꾸준한 기록이 마음 이해의 첫걸음이에요',
        timeLabel: '이번 주',
      ));
    }

    // ④ 최근 작성 완료 항목 (최근 14일, 최신순 최대 10개).
    final recent = recorded
        .where((d) =>
            !d.isAfter(today) && today.difference(d).inDays <= 14)
        .toList()
      ..sort((a, b) => b.compareTo(a));
    for (final day in recent.take(10)) {
      items.add(_NotifItem(
        icon: Icons.menu_book_rounded,
        title: '${DateFormatter.monthDay(day)} 일기가 기록되었어요',
        subtitle: '감정 리포트와 상담 기록도 함께 저장됐어요',
        timeLabel: _relativeLabel(day, today),
        onTap: () => goToDate(day, written: true),
      ));
    }

    return items;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = _buildItems(context, ref);

    return Scaffold(
      appBar: const OddoAppBar(title: '알림'),
      body: AppBackground(
        child: SafeArea(
          child: items.isEmpty
              ? const _EmptyState()
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.screenH),
                  children: [
                    OddoCard(
                      padding: EdgeInsets.zero,
                      child: Column(
                        children: [
                          for (var i = 0; i < items.length; i++) ...[
                            if (i > 0)
                              const Divider(
                                  color: AppColors.divider, height: 1),
                            _NotifRow(item: items[i]),
                          ],
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

class _NotifRow extends StatelessWidget {
  const _NotifRow({required this.item});
  final _NotifItem item;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: item.onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md, vertical: AppSpacing.sm),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: const BoxDecoration(
                    color: AppColors.primarySoft,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(item.icon, size: 18, color: AppColors.primary),
                ),
                if (item.unread)
                  Positioned(
                    top: -1,
                    right: -1,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: AppColors.primary,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.title,
                      style: AppTypography.body
                          .copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 1),
                  Text(item.subtitle, style: AppTypography.caption),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(item.timeLabel, style: AppTypography.caption),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const MascotImage(pose: MascotPose.front, size: 120),
          Gap.h16,
          Text('아직 알림이 없어요',
              style: AppTypography.subtitle
                  .copyWith(color: AppColors.textSecondary)),
          Gap.h4,
          const Text('일기를 기록하면 소식이 여기에 쌓여요',
              style: AppTypography.caption),
        ],
      ),
    );
  }
}
