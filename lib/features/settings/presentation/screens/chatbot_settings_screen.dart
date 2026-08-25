import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/error/app_exception.dart';
import '../../../../data/dummy/persona_dummy.dart';
import '../../../../features/persona/data/models/persona_config.dart';
import '../../../../features/persona/data/persona_providers.dart';
import '../../../../features/persona/presentation/widgets/persona_form.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/oddo_app_bar.dart';
import '../../../../widgets/primary_button.dart';

/// Auxiliary — 챗봇 설정. 온보딩에서 정한 페르소나(말투/성격/이름)를
/// 저장된 값으로 불러와 수정·저장한다. 폼 UI는 온보딩 화면(30)과
/// [PersonaForm]으로 공유. (Phase 5 상담봇 시스템 프롬프트의 소스)
class ChatbotSettingsScreen extends ConsumerStatefulWidget {
  const ChatbotSettingsScreen({super.key});

  @override
  ConsumerState<ChatbotSettingsScreen> createState() =>
      _ChatbotSettingsScreenState();
}

class _ChatbotSettingsScreenState
    extends ConsumerState<ChatbotSettingsScreen> {
  bool _saving = false;
  bool _initialized = false;

  int _toneIndex = 0;
  Set<int> _traits = {};
  String _name = PersonaDummy.defaultName;

  /// 저장된 설정을 폼 값(인덱스)으로 변환해 1회 초기화.
  void _initFrom(PersonaConfig? config) {
    if (_initialized) return;
    if (config == null) {
      _traits = {
        for (var i = 0; i < PersonaDummy.traits.length; i++)
          if (PersonaDummy.defaultTraits.contains(PersonaDummy.traits[i])) i,
      };
    } else {
      final toneIndex =
          PersonaDummy.tones.indexWhere((t) => t.title == config.tone);
      _toneIndex = toneIndex < 0 ? 0 : toneIndex;
      _traits = {
        for (var i = 0; i < PersonaDummy.traits.length; i++)
          if (config.traits.contains(PersonaDummy.traits[i])) i,
      };
      _name = config.name;
    }
    _initialized = true;
  }

  Future<void> _save() async {
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
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('챗봇 설정을 저장했어요.')));
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
    final personaAsync = ref.watch(personaConfigProvider);

    return Scaffold(
      appBar: const OddoAppBar(title: '챗봇 설정'),
      body: AppBackground(
        child: SafeArea(
          child: personaAsync.when(
            loading: () => _initialized
                // 저장 직후 재조회 중에도 폼 유지 (입력값 보존).
                ? _buildForm()
                : const Center(
                    child: CircularProgressIndicator(color: AppColors.primary),
                  ),
            error: (_, _) {
              _initFrom(null);
              return _buildForm();
            },
            data: (config) {
              _initFrom(config);
              return _buildForm();
            },
          ),
        ),
      ),
    );
  }

  Widget _buildForm() {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
                AppSpacing.lg, AppSpacing.screenH, AppSpacing.md),
            child: PersonaForm(
              initialToneIndex: _toneIndex,
              initialTraits: {..._traits},
              initialName: _name,
              onChanged: (tone, selectedTraits, newName) {
                _toneIndex = tone;
                _traits = selectedTraits;
                _name = newName;
              },
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.screenH,
              AppSpacing.xs, AppSpacing.screenH, AppSpacing.xs),
          child: PrimaryButton(
            label: '저장하기',
            loading: _saving,
            onPressed: _save,
          ),
        ),
      ],
    );
  }
}
