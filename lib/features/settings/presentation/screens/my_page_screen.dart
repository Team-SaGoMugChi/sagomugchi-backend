import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../core/utils/validators.dart';
import '../../../../features/auth/application/auth_controller.dart';
import '../../../../features/auth/data/auth_providers.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/oddo_app_bar.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/oddo_text_field.dart';

/// 이 계정이 비밀번호 로그인을 지원하는지 (소셜 전용 계정이면 false —
/// 비밀번호 변경 메뉴를 숨긴다).
final hasPasswordLoginProvider = FutureProvider<bool>((ref) {
  return ref.watch(authRepositoryProvider).hasPasswordLogin();
});

/// Auxiliary — 마이페이지. 프로필(닉네임 수정 가능) + 계정 작업:
/// 비밀번호 변경(이메일 계정만) / 로그아웃 / 회원 탈퇴.
class MyPageScreen extends ConsumerWidget {
  const MyPageScreen({super.key});

  Future<void> _editNickname(BuildContext context, WidgetRef ref) async {
    final current = ref.read(authControllerProvider).user?.nickname ?? '';
    final controller = TextEditingController(text: current);
    final saved = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('닉네임 수정', style: AppTypography.subtitle),
        content: OddoTextField(
          controller: controller,
          hint: '닉네임을 입력해주세요',
          prefixIcon: Icons.person_outline_rounded,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () {
              final name = controller.text.trim();
              final error = Validators.nickname(name);
              if (error != null) {
                ScaffoldMessenger.of(dialogContext)
                    .showSnackBar(SnackBar(content: Text(error)));
                return;
              }
              Navigator.of(dialogContext).pop(name);
            },
            child: const Text('저장',
                style: TextStyle(fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
    if (saved == null || saved == current) return;
    try {
      await ref.read(authControllerProvider.notifier).updateNickname(saved);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('닉네임을 변경했어요.')));
    } on AppException catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _changePassword(BuildContext context, WidgetRef ref) async {
    final email = ref.read(authControllerProvider).user?.email;
    if (email == null || email.isEmpty) return;
    final confirmed = await _confirm(
      context,
      title: '비밀번호를 변경할까요?',
      message: '$email 주소로 비밀번호 재설정 메일을 보내드려요.',
      confirmLabel: '메일 보내기',
    );
    if (confirmed != true) return;
    try {
      await ref
          .read(authControllerProvider.notifier)
          .sendPasswordReset(email: email);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('메일을 보냈어요. 받은 편지함을 확인해주세요.')));
    } on AppException catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final confirmed = await _confirm(
      context,
      title: '로그아웃할까요?',
      message: '다시 로그인하면 기록을 이어서 볼 수 있어요.',
      confirmLabel: '로그아웃',
    );
    if (confirmed != true) return;
    await ref.read(authControllerProvider.notifier).logout();
    if (context.mounted) context.goNamed(AppRoute.login);
  }

  Future<void> _deleteAccount(BuildContext context, WidgetRef ref) async {
    final confirmed = await _confirm(
      context,
      title: '정말 탈퇴할까요?',
      message: '계정과 모든 감정 기록이 삭제되며 되돌릴 수 없어요.',
      confirmLabel: '탈퇴하기',
      destructive: true,
    );
    if (confirmed != true) return;
    try {
      await ref.read(authControllerProvider.notifier).deleteAccount();
      if (context.mounted) context.goNamed(AppRoute.login);
    } on AppException catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<bool?> _confirm(
    BuildContext context, {
    required String title,
    required String message,
    required String confirmLabel,
    bool destructive = false,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(title, style: AppTypography.subtitle),
        content: Text(message, style: AppTypography.bodySecondary),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(
              confirmLabel,
              style: TextStyle(
                color: destructive ? AppColors.error : AppColors.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authControllerProvider.select((s) => s.user));
    final hasPassword = ref.watch(hasPasswordLoginProvider).value ?? false;

    return Scaffold(
      appBar: const OddoAppBar(title: '마이페이지'),
      body: AppBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screenH),
            children: [
              OddoCard(
                child: Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: const BoxDecoration(
                        color: AppColors.primarySoft,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.person_rounded,
                          size: 30, color: AppColors.primary),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(user?.nickname ?? '로그인이 필요해요',
                              style: AppTypography.subtitle),
                          const SizedBox(height: 2),
                          Text(user?.email ?? '-',
                              style: AppTypography.bodySecondary),
                        ],
                      ),
                    ),
                    if (user != null)
                      IconButton(
                        icon: const Icon(Icons.edit_rounded,
                            size: 20, color: AppColors.textTertiary),
                        onPressed: () => _editNickname(context, ref),
                      ),
                  ],
                ),
              ),
              Gap.h16,
              OddoCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    if (hasPassword) ...[
                      _MenuRow(
                        icon: Icons.lock_outline_rounded,
                        label: '비밀번호 변경',
                        onTap: () => _changePassword(context, ref),
                      ),
                      const Divider(color: AppColors.divider, height: 1),
                    ],
                    _MenuRow(
                      icon: Icons.logout_rounded,
                      label: '로그아웃',
                      onTap: () => _logout(context, ref),
                    ),
                    const Divider(color: AppColors.divider, height: 1),
                    _MenuRow(
                      icon: Icons.person_off_outlined,
                      label: '회원 탈퇴',
                      color: AppColors.error,
                      onTap: () => _deleteAccount(context, ref),
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

class _MenuRow extends StatelessWidget {
  const _MenuRow({
    required this.icon,
    required this.label,
    required this.onTap,
    this.color,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md, vertical: AppSpacing.md),
        child: Row(
          children: [
            Icon(icon, size: 20, color: color ?? AppColors.textSecondary),
            const SizedBox(width: AppSpacing.sm),
            Text(label,
                style: AppTypography.body.copyWith(
                    color: color ?? AppColors.textStrong,
                    fontWeight: FontWeight.w600)),
            const Spacer(),
            const Icon(Icons.chevron_right_rounded,
                color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }
}
