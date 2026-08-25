import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/validators.dart';
import '../../../../data/dummy/auth_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/oddo_text_field.dart';
import '../../../../widgets/primary_button.dart';
import '../../application/auth_controller.dart';
import '../widgets/auth_form_header.dart';
import '../widgets/gender_selector.dart';
import '../widgets/terms_agreement_section.dart';

/// Screen 3 — 회원가입. Creates a Firebase account + `users/{uid}` profile.
/// (생년월일/성별 are collected UI-only for now — not in schema v1.)
class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key});

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _passwordConfirmController = TextEditingController();
  final _nicknameController = TextEditingController();

  String? _emailError;
  String? _passwordError;
  String? _passwordConfirmError;
  String? _nicknameError;
  DateTime? _birth;
  bool _requiredTermsChecked = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _passwordConfirmController.dispose();
    _nicknameController.dispose();
    super.dispose();
  }

  Future<void> _pickBirth() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _birth ?? DateTime(now.year - 20),
      firstDate: DateTime(1900),
      lastDate: now,
    );
    if (picked != null) setState(() => _birth = picked);
  }

  Future<void> _submit() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    final nickname = _nicknameController.text.trim();
    setState(() {
      _emailError = Validators.email(email);
      _passwordError = Validators.password(password);
      _passwordConfirmError = Validators.passwordConfirm(
          _passwordConfirmController.text, password);
      _nicknameError = Validators.nickname(nickname);
    });
    if (_emailError != null ||
        _passwordError != null ||
        _passwordConfirmError != null ||
        _nicknameError != null) {
      return;
    }
    if (!_requiredTermsChecked) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('필수 약관에 동의해주세요.')),
      );
      return;
    }

    try {
      await ref.read(authControllerProvider.notifier).signUp(
            email: email,
            password: password,
            nickname: nickname,
          );
      if (mounted) context.goNamed(AppRoute.home);
    } on AppException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLoading =
        ref.watch(authControllerProvider.select((s) => s.isLoading));

    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH, AppSpacing.xs, AppSpacing.screenH, AppSpacing.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // TODO: 하트를 든 환영 포즈로 교체 예정 (character_sheet 12.하트 들기)
                const AuthFormHeader(
                  title: '회원가입',
                  subtitle: 'Oddo와 함께\n오늘 감정을 기록해요.',
                  mascotPose: MascotPose.heart,
                ),
                Gap.h20,
                OddoCard(
                  child: Column(
                    children: [
                      OddoTextField(
                        controller: _emailController,
                        hint: AuthDummy.emailHint,
                        prefixIcon: Icons.mail_outline_rounded,
                        keyboardType: TextInputType.emailAddress,
                        errorText: _emailError,
                      ),
                      Gap.h12,
                      OddoTextField(
                        controller: _passwordController,
                        hint: AuthDummy.passwordHint,
                        prefixIcon: Icons.lock_outline_rounded,
                        obscure: true,
                        errorText: _passwordError,
                      ),
                      Gap.h12,
                      OddoTextField(
                        controller: _passwordConfirmController,
                        hint: AuthDummy.passwordConfirmHint,
                        prefixIcon: Icons.lock_outline_rounded,
                        obscure: true,
                        errorText: _passwordConfirmError,
                      ),
                      Gap.h12,
                      OddoTextField(
                        controller: _nicknameController,
                        hint: AuthDummy.nicknameHint,
                        prefixIcon: Icons.person_outline_rounded,
                        errorText: _nicknameError,
                      ),
                      Gap.h12,
                      OddoTextField(
                        hint: _birth != null
                            ? DateFormatter.dotted(_birth!)
                            : AuthDummy.birthHint,
                        prefixIcon: Icons.calendar_today_outlined,
                        readOnly: true,
                        onTap: _pickBirth,
                        suffix: const Icon(Icons.calendar_month_rounded,
                            size: 20, color: AppColors.primary),
                      ),
                      Gap.h12,
                      const GenderSelector(),
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: AppSpacing.md),
                        child: Divider(color: AppColors.divider),
                      ),
                      TermsAgreementSection(
                        onRequiredChanged: (ok) =>
                            setState(() => _requiredTermsChecked = ok),
                      ),
                    ],
                  ),
                ),
                Gap.h24,
                PrimaryButton(
                  label: '회원가입 완료',
                  loading: isLoading,
                  onPressed: _submit,
                ),
                Gap.h12,
                _loginRow(context),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _loginRow(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text('이미 계정이 있으신가요?', style: AppTypography.bodySecondary),
        const SizedBox(width: 6),
        GestureDetector(
          onTap: () =>
              context.canPop() ? context.pop() : context.goNamed(AppRoute.login),
          child: Text(
            '로그인',
            style: AppTypography.bodySecondary
                .copyWith(color: AppColors.primary, fontWeight: FontWeight.w700),
          ),
        ),
      ],
    );
  }
}
