import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:oddo/features/diary/data/models/counsel_session.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../data/dummy/records_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/chat_bubble.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/primary_button.dart';
import '../../../diary/data/diary_providers.dart';
import '../../application/viewing_date_provider.dart';
import '../widgets/record_async_view.dart';
import '../widgets/record_top_bar.dart';

/// Screen 50 — 상담 기록 (상담 tab of the written-day context). Shows the
/// viewed date's saved counsel log from Firestore.
class CounselRecordScreen extends ConsumerWidget {
  const CounselRecordScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final date = ref.watch(viewingDateProvider);
    final counselAsync = ref.watch(counselSessionProvider(date));

    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          // 필터 아이콘 제거: 날짜당 세션이 1개라 필터 대상이 없음
          // (다중 세션이 생기면 복원).
          const RecordTopBar(title: '상담 기록'),
          Expanded(
            child: RecordAsyncView(
              value: counselAsync,
              emptyMessage: '이 날짜에는 아직 상담 기록이 없어요',
              builder: (session) => ListView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.md),
                children: [
                  Text(RecordsDummy.counselTitle(date),
                      style: AppTypography.subtitle),
                  Gap.h12,
                  _SessionHeader(session: session),
                  Gap.h16,
                  for (final msg in session.messages)
                    ChatBubble(
                        fromOddo: msg.speaker == CounselSpeaker.oddo,
                        text: msg.text),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
            child: PrimaryButton(
              label: '상담 이어하기',
              leadingIcon: Icons.videocam_rounded,
              onPressed: () =>
                  context.pushNamed(AppRoute.diaryStep4CounselCall),
            ),
          ),
        ],
      ),
    );
  }
}

class _SessionHeader extends StatelessWidget {
  const _SessionHeader({required this.session});
  final CounselSession session;

  @override
  Widget build(BuildContext context) {
    return OddoCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: const BoxDecoration(
                color: AppColors.primarySoft, shape: BoxShape.circle),
            child: const Icon(Icons.videocam_rounded,
                size: 20, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(RecordsDummy.counselSessionLabel,
                    style: AppTypography.body
                        .copyWith(fontWeight: FontWeight.w600)),
                Text(
                    '${DateFormatter.hhmm(session.startedAt)} - ${DateFormatter.hhmm(session.endedAt)}',
                    style: AppTypography.caption),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded,
              color: AppColors.textTertiary),
        ],
      ),
    );
  }
}
