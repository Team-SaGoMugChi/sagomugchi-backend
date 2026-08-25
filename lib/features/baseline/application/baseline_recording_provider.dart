import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Path of the voice file recorded during baseline 측정 (screen 19).
/// Phase 4 uploads it to the AI server to compute the voice baseline.
class BaselineRecording extends Notifier<String?> {
  @override
  String? build() => null;

  void set(String path) => state = path;
}

final baselineRecordingProvider =
    NotifierProvider<BaselineRecording, String?>(BaselineRecording.new);
