import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../error/app_exception.dart';

/// Thin wrapper over [SharedPreferences] for small on-device state
/// (onboarding-complete flag, keep-logged-in, persona selection, …).
///
/// Keys live here as constants so features don't scatter magic strings.
/// Larger/structured data (diaries, reports) belongs in Firestore, not here.
class LocalStore {
  LocalStore(this._prefs);

  final SharedPreferences _prefs;

  // ── Well-known keys ────────────────────────────────────────────────────
  static const String kOnboardingComplete = 'onboarding_complete';
  static const String kKeepLoggedIn = 'keep_logged_in';
  static const String kPersonaId = 'persona_id';
  static const String kRecordedDays = 'recorded_days'; // ISO date strings

  /// 일기 리마인더 알림 on/off (Phase 7 로컬 푸시의 스위치).
  static const String kReminderEnabled = 'reminder_enabled';

  bool getBool(String key, {bool fallback = false}) =>
      _prefs.getBool(key) ?? fallback;

  String? getString(String key) => _prefs.getString(key);

  List<String> getStringList(String key) => _prefs.getStringList(key) ?? [];

  Future<void> setBool(String key, bool value) =>
      _guard(() => _prefs.setBool(key, value));

  Future<void> setString(String key, String value) =>
      _guard(() => _prefs.setString(key, value));

  Future<void> setStringList(String key, List<String> value) =>
      _guard(() => _prefs.setStringList(key, value));

  Future<void> remove(String key) => _guard(() => _prefs.remove(key));

  /// Clears everything — for logout/withdrawal flows.
  Future<void> clear() => _guard(_prefs.clear);

  Future<void> _guard(Future<bool> Function() write) async {
    try {
      await write();
    } catch (e) {
      throw CacheException('Failed to write local store', e);
    }
  }
}

/// App-wide [LocalStore]. Overridden in `bootstrap()` with a real
/// [SharedPreferences] instance; throws if the override is missing so we
/// never silently run without persistence.
final localStoreProvider = Provider<LocalStore>(
  (ref) => throw UnimplementedError(
    'localStoreProvider must be overridden in bootstrap() with a LocalStore',
  ),
);
