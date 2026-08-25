import 'package:permission_handler/permission_handler.dart';

/// Camera/microphone permission helpers — the two permissions Oddo needs
/// (표정 분석·음성 기록). Wraps permission_handler so screens don't deal with
/// per-permission statuses.
abstract final class AppPermissions {
  AppPermissions._();

  /// Requests camera + microphone. Returns true when both are granted.
  static Future<bool> requestCameraAndMic() async {
    try {
      final statuses =
          await [Permission.camera, Permission.microphone].request();
      return statuses.values.every((s) => s.isGranted);
    } catch (_) {
      // Platform channel unavailable (tests) — treat as not granted.
      return false;
    }
  }

  /// True when either permission is permanently denied, meaning the OS prompt
  /// won't show again and the user must enable it in Settings.
  static Future<bool> isPermanentlyDenied() async {
    try {
      final camera = await Permission.camera.status;
      final mic = await Permission.microphone.status;
      return camera.isPermanentlyDenied || mic.isPermanentlyDenied;
    } catch (_) {
      return false;
    }
  }

  /// Opens the app's OS settings page (for the permanently-denied case).
  static Future<void> openSettings() => openAppSettings();
}
