import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config_provider.dart';
import '../../../core/network/api_client.dart';
import 'datasources/baseline_data_source.dart';
import 'datasources/baseline_dummy_data_source.dart';
import 'datasources/baseline_remote_data_source.dart';
import 'repositories/baseline_repository.dart';
import 'repositories/baseline_repository_impl.dart';

/// Swap point: dummy vs real data source, chosen by [AppConfig] (diary와 동일 패턴).
final baselineDataSourceProvider = Provider<BaselineDataSource>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.useDummyData) {
    return BaselineDummyDataSource();
  }
  return BaselineRemoteDataSource(ref.watch(apiClientProvider));
});

final baselineRepositoryProvider = Provider<BaselineRepository>((ref) {
  return BaselineRepositoryImpl(ref.watch(baselineDataSourceProvider));
});
