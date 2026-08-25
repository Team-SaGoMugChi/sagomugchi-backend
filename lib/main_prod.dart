import 'app/app.dart';
import 'core/config/app_config.dart';

/// Prod flavor entrypoint. Runs against real backends (no dummy data).
///
/// Build/run with the AI-server URL injected:
/// `flutter run -t lib/main_prod.dart --dart-define=ODDO_API_BASE_URL=https://...`
void main() => bootstrap(AppConfig.prod);
