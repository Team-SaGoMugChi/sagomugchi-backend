import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/primary_button.dart';

/// Screen 5 — 로그인 실패 모달. Soft, reassuring error dialog over the login
/// screen. [message] carries the per-case copy (계정 없음 / 비밀번호 오류 /
/// 네트워크 — the AuthException message); omitted → generic copy.
Future<void> showLoginErrorModal(BuildContext context, {String? message}) {
  return showDialog<void>(
    context: context,
    builder: (dialogContext) => Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.card),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg, AppSpacing.sm, AppSpacing.lg, AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: IconButton(
                icon: const Icon(Icons.close_rounded,
                    color: AppColors.textTertiary),
                onPressed: () => Navigator.of(dialogContext).pop(),
              ),
            ),
            // TODO: 미안해하는 표정 포즈로 교체 예정 (character_sheet 07.사방면/미안한 표정)
            const MascotImage(pose: MascotPose.sorry, size: 88),
            Gap.h16,
            const Text('로그인 정보를 다시 확인해 주세요',
                textAlign: TextAlign.center, style: AppTypography.subtitle),
            Gap.h8,
            Text(
              message ?? '이메일 또는 비밀번호가 올바르지 않아요.\n다시 입력하거나 비밀번호를 재설정할 수 있어요.',
              textAlign: TextAlign.center,
              style: AppTypography.bodySecondary,
            ),
            Gap.h24,
            PrimaryButton(
              label: '다시 입력하기',
              onPressed: () => Navigator.of(dialogContext).pop(),
            ),
            Gap.h8,
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                context.pushNamed(AppRoute.findPassword);
              },
              child: const Text('비밀번호 찾기'),
            ),
          ],
        ),
      ),
    ),
  );
}
