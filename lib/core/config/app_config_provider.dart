import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_config.dart';

/// Exposes the active [AppConfig] to the whole app.
///
/// It throws by default on purpose: the flavor entrypoint must override it in
/// `ProviderScope(overrides: [...])` via `bootstrap()`. This guarantees we
/// never silently run with the wrong environment.
final appConfigProvider = Provider<AppConfig>(
  (ref) => throw UnimplementedError(
    'appConfigProvider must be overridden in bootstrap() with an AppConfig',
  ),
);
