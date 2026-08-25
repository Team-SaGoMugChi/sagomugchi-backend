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
import '../../../../widgets/app_background.dart';
import '../../../../widgets/oddo_card.dart';
import '../../../../widgets/oddo_text_field.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/security_note.dart';
import '../../application/auth_controller.dart';
import '../widgets/auth_form_header.dart';
import '../widgets/gender_selector.dart';
import '../widgets/terms_agreement_section.dart';

/// Screen 4 — 소셜 로그인 추가 정보 입력. First-time social users complete the
/// profile (nickname + 필수 약관) → `users/{uid}` created → home.
/// (생년월일/성별 are collected UI-only for now — not in schema v1.)
class SocialExtraInfoScreen extends ConsumerStatefulWidget {
  const SocialExtraInfoScreen({super.key});

  @override
  ConsumerState<SocialExtraInfoScreen> createState() =>
      _SocialExtraInfoScreenState();
}

class _SocialExtraInfoScreenState extends ConsumerState<SocialExtraInfoScreen> {
  final _nicknameController = TextEditingController();

  String? _nicknameError;
  DateTime? _birth;
  bool _requiredTermsChecked = false;

  @override
  void dispose() {
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
    final nickname = _nicknameController.text.trim();
    setState(() => _nicknameError = Validators.nickname(nickname));
    if (_nicknameError != null) return;
    if (!_requiredTermsChecked) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('필수 약관에 동의해주세요.')),
      );
      return;
    }

    try {
      await ref
          .read(authControllerProvider.notifier)
          .completeSocialProfile(nickname: nickname);
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
                // TODO: 반갑게 인사하는 포즈로 교체 예정 (character_sheet 12.하트 들기 / 10.인사)
                const AuthFormHeader(
                  title: '추가 정보 입력',
                  subtitle: '더 나은 맞춤 대화를 위해\n몇 가지만 알려주세요.',
                  mascotPose: MascotPose.heart,
                ),
                Gap.h20,
                OddoCard(
                  child: Column(
                    children: [
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
                  label: '시작하기',
                  loading: isLoading,
                  onPressed: _submit,
                ),
                Gap.h16,
                const SecurityNote(
                  text: '입력하신 정보는 안전하게 보호되며, 감정분석과 맞춤 대화 서비스에 사용됩니다.',
                  center: true,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
