import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config_provider.dart';
import 'datasources/auth_data_source.dart';
import 'datasources/auth_dummy_data_source.dart';
import 'datasources/auth_firebase_data_source.dart';
import 'repositories/auth_repository.dart';
import 'repositories/auth_repository_impl.dart';

/// THE swap point: dummy vs real data source, chosen by [AppConfig].
/// Tests override the config with `useDummyData: true` to stay off Firebase.
final authDataSourceProvider = Provider<AuthDataSource>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.useDummyData) {
    return AuthDummyDataSource();
  }
  return AuthFirebaseDataSource();
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepositoryImpl(ref.watch(authDataSourceProvider));
});
