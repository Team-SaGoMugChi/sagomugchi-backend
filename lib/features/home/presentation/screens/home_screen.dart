import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/home_dummy.dart';
import '../../../../data/dummy/records_dummy.dart';
import '../../../../features/onboarding/application/onboarding_controller.dart';
import '../../../../features/records/application/recorded_days_provider.dart';
import '../../../../features/records/application/viewing_date_provider.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/diary_bottom_nav.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/primary_button.dart';
import '../widgets/baseline_needed_dialog.dart';
import '../widgets/diary_start_modal.dart';
import '../widgets/home_header.dart';
import '../widgets/weekly_calendar.dart';

/// Screens 7 & 47 — 홈. One interactive component: the weekly bar re-centers on
/// the selected date (held in [viewingDateProvider]) and the main card switches
/// by whether that date has a diary record. Written day → video card +
/// [일기][리포트][상담] tab bar; not-written → the "write a diary" CTA card.
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // Before onboarding, auto-open the first-measurement popup once on entry.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !ref.read(onboardingCompleteProvider)) {
        showBaselineNeededDialog(context);
      }
    });
  }

  void _onWritePressed(bool onboarded, DateTime date) {
    if (onboarded) {
      showDiaryStartModal(context, ref, date: date);
    } else {
      showBaselineNeededDialog(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final selected = ref.watch(viewingDateProvider);
    final onboarded = ref.watch(onboardingCompleteProvider);
    final recorded = ref.watch(recordedDaysProvider);
    final written = recorded.contains(
      DateTime(selected.year, selected.month, selected.day),
    );
    // 7-day strip centered on the selected date (selected in the middle).
    final weekDays = List.generate(
      7,
      (i) => selected.add(Duration(days: i - 3)),
    );

    return Scaffold(
      bottomNavigationBar: written
          ? DiaryBottomNav(
              currentIndex: 0,
              onSelect: (i) {
                if (i == 1) context.goNamed(AppRoute.recordsReport);
                if (i == 2) context.goNamed(AppRoute.recordsCounsel);
              },
            )
          : null,
      body: AppBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.xs,
                  AppSpacing.screenH,
                  0,
                ),
                child: HomeHeader(month: selected),
              ),
              Gap.h12,
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.screenH,
                ),
                child: WeeklyCalendar(
                  days: weekDays,
                  today: HomeDummy.today,
                  selected: selected,
                  recordedDays: recorded,
                  onSelect: (d) =>
                      ref.read(viewingDateProvider.notifier).set(d),
                ),
              ),
              Expanded(
                // 위 기준 고정 정렬: 작성일에만 하단 탭바가 생겨도 카드가
                // 세로로 밀리지 않도록, 화면 중앙 정렬 대신 주간 바 아래
                // 고정 오프셋에 카드를 둔다.
                child: Align(
                  alignment: Alignment.topCenter,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.screenH,
                      AppSpacing.xl,
                      AppSpacing.screenH,
                      AppSpacing.md,
                    ),
                    child: Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Padding(
                          // 마스코트 박스(170) - 겹침(14) = 카드 시작 오프셋.
                          padding: const EdgeInsets.only(top: 156),
                          child: _HomeCard(
                            date: selected,
                            written: written,
                            onReadDiary: () =>
                                context.goNamed(AppRoute.recordsDiary),
                            onWrite: () => _onWritePressed(onboarded, selected),
                          ),
                        ),
                        // 카드 위 레이어: 빼꼼 포즈의 양손이 카드 윗변을 잡는
                        // 연출 (이미지 하단 = 손끝이라 카드 내용은 안 가림).
                        const Positioned(
                          top: 0,
                          left: 0,
                          right: 0,
                          child: Center(
                            child: MascotImage(
                              pose: MascotPose.peeking,
                              size: 170,
                              alignment: Alignment.bottomCenter,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The home's single main card. Both states render inside one shell via
/// [IndexedStack], which sizes itself to the larger child (the written
/// layout) — so the card's size and position never change when the selected
/// date flips between written/unwritten; only the content swaps.
class _HomeCard extends StatelessWidget {
  const _HomeCard({
    required this.date,
    required this.written,
    required this.onReadDiary,
    required this.onWrite,
  });

  final DateTime date;
  final bool written;
  final VoidCallback onReadDiary;
  final VoidCallback onWrite;

  @override
  Widget build(BuildContext context) {
    return _HomeCardShell(
      child: Stack(
        children: [
          // 작성일 내용은 항상 레이아웃에 참여(maintainSize)해서 카드
          // 크기를 고정하는 기준이 된다. 미작성일에는 보이지만 않게.
          Visibility(
            visible: written,
            maintainSize: true,
            maintainAnimation: true,
            maintainState: true,
            child: _WrittenContent(date: date, onReadDiary: onReadDiary),
          ),
          // 미작성 내용은 고정된 카드 영역 전체를 채우며 렌더링
          // (날짜 좌상단 / 히어로 중앙 / 버튼 하단).
          if (!written)
            Positioned.fill(
              child: _WriteContent(date: date, onWrite: onWrite),
            ),
        ],
      ),
    );
  }
}

/// Not-written state — prompt to start a diary for [date]. 파란 날짜는
/// 작성일 카드와 같은 스타일로 좌상단, 히어로(아이콘+문구)는 중앙, 작성
/// 버튼은 하단 고정.
class _WriteContent extends StatelessWidget {
  const _WriteContent({required this.date, required this.onWrite});

  final DateTime date;
  final VoidCallback onWrite;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 미작성일은 회색 날짜 — 파랑(기록 있음)/회색(기록 없음)으로
        // 상태를 색으로 구분 (월간 캘린더 배지와 동일한 규칙).
        Text(
          DateFormatter.monthDay(date),
          style: AppTypography.title.copyWith(color: AppColors.textTertiary),
        ),
        Expanded(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: const BoxDecoration(
                  color: AppColors.backgroundAlt,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.edit_note_rounded,
                  color: AppColors.textTertiary,
                ),
              ),
              Gap.h12,
              const Text(
                HomeDummy.writeCardTitle,
                textAlign: TextAlign.center,
                style: AppTypography.title,
              ),
              Gap.h8,
              const Text(
                HomeDummy.writeCardSubtitle,
                textAlign: TextAlign.center,
                style: AppTypography.bodySecondary,
              ),
            ],
          ),
        ),
        PrimaryButton(label: '일기 작성하기', onPressed: onWrite),
      ],
    );
  }
}

/// Written state — recorded-day card content with the generated video +
/// read button.
class _WrittenContent extends StatelessWidget {
  const _WrittenContent({required this.date, required this.onReadDiary});

  final DateTime date;
  final VoidCallback onReadDiary;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          DateFormatter.monthDay(date),
          style: AppTypography.title.copyWith(color: AppColors.primary),
        ),
        Gap.h4,
        const Text(
          RecordsDummy.homeWrittenTitle,
          style: AppTypography.bodySecondary,
        ),
        Gap.h16,
        GestureDetector(
          onTap: () => context.pushNamed(AppRoute.shortformPlayer),
          child: ClipRRect(
            borderRadius: AppRadius.card,
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Container(color: AppColors.callBackground),
                  // TODO: 일기 쓰는 장면 영상 썸네일로 교체 예정
                  const Center(
                    child: MascotImage(
                      pose: MascotPose.writing,
                      size: 96,
                      onDark: true,
                    ),
                  ),
                  const Center(
                    child: Icon(
                      Icons.play_circle_fill_rounded,
                      size: 48,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        Gap.h16,
        GestureDetector(
          onTap: onReadDiary,
          child: Container(
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: const BoxDecoration(
              color: AppColors.backgroundAlt,
              borderRadius: AppRadius.button,
            ),
            child: Row(
              children: [
                const Icon(
                  Icons.menu_book_rounded,
                  size: 20,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 10),
                Text(
                  '작성한 일기 읽기',
                  style: AppTypography.body.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                const Icon(
                  Icons.chevron_right_rounded,
                  color: AppColors.textTertiary,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Shared white rounded card shell for both home states.
class _HomeCardShell extends StatelessWidget {
  const _HomeCardShell({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.card,
        boxShadow: [
          BoxShadow(
            color: Color(0x0F000000),
            blurRadius: 20,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}
