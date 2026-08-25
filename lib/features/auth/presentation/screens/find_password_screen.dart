import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../core/utils/validators.dart';
import '../../../../data/dummy/auth_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_text_field.dart';
import '../../../../widgets/oddo_wordmark.dart';
import '../../../../widgets/primary_button.dart';
import '../../application/auth_controller.dart';
import '../widgets/or_divider.dart';

/// Screen 6 — 비밀번호 찾기. Enter email → send a real reset mail → back to
/// login. (Whether the email is registered is intentionally not revealed.)
class FindPasswordScreen extends ConsumerStatefulWidget {
  const FindPasswordScreen({super.key});

  @override
  ConsumerState<FindPasswordScreen> createState() =>
      _FindPasswordScreenState();
}

class _FindPasswordScreenState extends ConsumerState<FindPasswordScreen> {
  final _emailController = TextEditingController();
  String? _emailError;
  bool _sending = false;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _sendAndReturn() async {
    final email = _emailController.text.trim();
    setState(() => _emailError = Validators.email(email));
    if (_emailError != null) return;

    setState(() => _sending = true);
    try {
      await ref
          .read(authControllerProvider.notifier)
          .sendPasswordReset(email: email);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('메일을 보냈어요. 받은 편지함을 확인해주세요.')),
      );
      if (context.canPop()) context.pop();
    } on AppException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH, 0, AppSpacing.screenH, AppSpacing.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
                    onPressed: () => context.pop(),
                  ),
                ),
                Gap.h8,
                const OddoWordmark(fontSize: 28),
                Gap.h12,
                const Text('비밀번호 찾기',
                    textAlign: TextAlign.center, style: AppTypography.title),
                Gap.h8,
                const Text(
                  '가입한 이메일을 입력하면\n비밀번호 재설정 안내를 보내드릴게요.',
                  textAlign: TextAlign.center,
                  style: AppTypography.bodySecondary,
                ),
                Gap.h24,
                // TODO: 편지를 든 포즈로 교체 예정 (character_sheet 기반 편지 들기)
                const MascotImage(pose: MascotPose.letter, size: 150),
                Gap.h24,
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text('이메일 주소',
                      style: AppTypography.bodySecondary,
                      textAlign: TextAlign.left),
                ),
                Gap.h8,
                OddoTextField(
                  controller: _emailController,
                  hint: AuthDummy.emailHint,
                  prefixIcon: Icons.mail_outline_rounded,
                  keyboardType: TextInputType.emailAddress,
                  errorText: _emailError,
                ),
                Gap.h20,
                PrimaryButton(
                  label: '재설정 메일 보내기',
                  trailingIcon: Icons.chevron_right_rounded,
                  loading: _sending,
                  onPressed: _sendAndReturn,
                ),
                Gap.h16,
                const OrDivider(),
                Gap.h8,
                TextButton(
                  onPressed: () => context.pop(),
                  child: const Text('로그인 화면으로 돌아가기'),
                ),
                Gap.h16,
                const _HelpCard(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Bottom tinted help card: "이메일을 찾을 수 없나요?" → 고객센터.
class _HelpCard extends StatelessWidget {
  const _HelpCard();

  /// 메일 앱으로 문의 — 앱이 없으면 주소를 클립보드에 복사.
  Future<void> _contactSupport(BuildContext context) async {
    final uri = Uri(
      scheme: 'mailto',
      path: AppConfig.supportEmail,
      queryParameters: {'subject': '[Oddo] 문의'},
    );
    final launched = await launchUrl(uri).catchError((_) => false);
    if (launched || !context.mounted) return;
    await Clipboard.setData(
        const ClipboardData(text: AppConfig.supportEmail));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
          content: Text('메일 앱을 열 수 없어 주소를 복사했어요: ${AppConfig.supportEmail}')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: const BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: AppRadius.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.verified_user_outlined,
                  size: 16, color: AppColors.primary),
              const SizedBox(width: 6),
              Text('이메일을 찾을 수 없나요?',
                  style: AppTypography.bodySecondary
                      .copyWith(fontWeight: FontWeight.w700)),
            ],
          ),
          Gap.h8,
          const Text('가입한 이메일이 기억나지 않는다면, 고객센터로 문의해 주세요.',
              style: AppTypography.caption),
          Gap.h8,
          GestureDetector(
            onTap: () => _contactSupport(context),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('고객센터 문의하기',
                    style: AppTypography.bodySecondary.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600)),
                const Icon(Icons.chevron_right_rounded,
                    size: 18, color: AppColors.primary),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
