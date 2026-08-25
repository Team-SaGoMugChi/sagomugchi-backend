import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:oddo/app/app.dart';
import 'package:oddo/core/config/app_config.dart';
import 'package:oddo/core/config/app_config_provider.dart';
import 'package:oddo/core/storage/local_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Tests run on dummy data so they never touch Firebase.
const _testConfig = AppConfig(
  environment: AppEnvironment.dev,
  appName: 'Oddo (test)',
  apiBaseUrl: '',
  useDummyData: true,
);

void main() {
  testWidgets('App boots into the splash screen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appConfigProvider.overrideWithValue(_testConfig),
          localStoreProvider.overrideWithValue(LocalStore(prefs)),
        ],
        child: const OddoApp(),
      ),
    );
    await tester.pump();

    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.text('Oddo'), findsWidgets);

    // Flush the splash session-restore delay so no timers stay pending.
    await tester.pump(const Duration(seconds: 2));
  });
}
