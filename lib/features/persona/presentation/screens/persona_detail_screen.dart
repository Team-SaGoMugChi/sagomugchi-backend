import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/error/app_exception.dart';
import '../../../../data/dummy/persona_dummy.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/primary_button.dart';
import '../../../../widgets/progress_dots.dart';
import '../../data/models/persona_config.dart';
import '../../data/persona_providers.dart';
import '../widgets/persona_form.dart';

/// Screen 30 — 챗봇 페르소나 설정 상세 (말투 / 성격 / 이름). 완료 시
/// `users/{uid}/meta/persona`에 저장 → 설정 완료 화면.
/// 폼 UI는 챗봇 설정 화면과 [PersonaForm]으로 공유.
class PersonaDetailScreen extends ConsumerStatefulWidget {
  const PersonaDetailScreen({super.key});

  @override
  ConsumerState<PersonaDetailScreen> createState() =>
      _PersonaDetailScreenState();
}

class _PersonaDetailScreenState extends ConsumerState<PersonaDetailScreen> {
  bool _saving = false;

  int _toneIndex = 0;
  Set<int> _traits = {
    for (var i = 0; i < PersonaDummy.traits.length; i++)
      if (PersonaDummy.defaultTraits.contains(PersonaDummy.traits[i])) i,
  };
  String _name = PersonaDummy.defaultName;

  Future<void> _saveAndContinue() async {
    final name = _name.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('챗봇 이름을 입력해주세요.')));
      return;
    }
    final config = PersonaConfig(
      name: name,
      tone: PersonaDummy.tones[_toneIndex].title,
      traits: [
        for (var i = 0; i < PersonaDummy.traits.length; i++)
          if (_traits.contains(i)) PersonaDummy.traits[i],
      ],
      updatedAt: DateTime.now(),
    );

    setState(() => _saving = true);
    try {
      await ref.read(personaRepositoryProvider).savePersona(config);
      ref.invalidate(personaConfigProvider);
      if (mounted) await context.pushNamed(AppRoute.personaDone);
    } on AppException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
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
                    child: Text('페르소나 설정',
                        textAlign: TextAlign.center,
                        style: AppTypography.subtitle),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              const ProgressDots(count: 3, current: 1),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                      AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
                  child: PersonaForm(
                    onChanged: (tone, traits, name) {
                      _toneIndex = tone;
                      _traits = traits;
                      _name = name;
                    },
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                    AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
                child: PrimaryButton(
                  label: '다음',
                  loading: _saving,
                  onPressed: _saveAndContinue,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
