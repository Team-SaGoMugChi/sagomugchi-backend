import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config_provider.dart';
import 'models/persona_config.dart';
import 'repositories/persona_repository.dart';

/// Swap point: dummy vs Firestore, chosen by [AppConfig].
final personaRepositoryProvider = Provider<PersonaRepository>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.useDummyData) {
    return PersonaDummyRepository();
  }
  return PersonaFirestoreRepository();
});

/// 저장된 페르소나 설정 (없으면 null). 설정 홈의 미리보기와 챗봇 설정
/// 화면이 watch — 저장 후에는 invalidate로 갱신.
final personaConfigProvider = FutureProvider<PersonaConfig?>((ref) {
  return ref.watch(personaRepositoryProvider).fetchPersona();
});
