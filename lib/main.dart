import 'app/app.dart';
import 'core/config/app_config.dart';

/// Dev flavor entrypoint. Runs the app on dummy data.
/// (A future `main_prod.dart` would call `bootstrap(AppConfig.prod)`.)
void main() => bootstrap(AppConfig.dev);
