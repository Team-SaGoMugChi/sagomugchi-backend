import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';

/// Standard async wrapper for the record screens (48–50): spinner while
/// loading, friendly copy on error or when the date has no record, and
/// [builder] once data arrives.
class RecordAsyncView<T> extends StatelessWidget {
  const RecordAsyncView({
    super.key,
    required this.value,
    required this.builder,
    this.emptyMessage = '이 날짜에는 아직 기록이 없어요',
  });

  final AsyncValue<T?> value;
  final Widget Function(T data) builder;
  final String emptyMessage;

  @override
  Widget build(BuildContext context) {
    return value.when(
      loading: () => const Center(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.xxl),
          child: CircularProgressIndicator(color: AppColors.primary),
        ),
      ),
      error: (_, _) => const _Message(
        icon: Icons.cloud_off_rounded,
        text: '기록을 불러오지 못했어요.\n잠시 후 다시 시도해주세요.',
      ),
      data: (data) => data == null
          ? _Message(icon: Icons.edit_note_rounded, text: emptyMessage)
          : builder(data),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: AppColors.textTertiary),
            Gap.h12,
            Text(text,
                textAlign: TextAlign.center,
                style: AppTypography.bodySecondary),
          ],
        ),
      ),
    );
  }
}
