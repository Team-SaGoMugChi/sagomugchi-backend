import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Path of the still face photo captured during baseline 측정 (screen 19).
/// Mirrors [baselineRecordingProvider] for the voice file.
class BaselineFaceImage extends Notifier<String?> {
  @override
  String? build() => null;

  void set(String path) => state = path;
}

final baselineFaceImageProvider =
    NotifierProvider<BaselineFaceImage, String?>(BaselineFaceImage.new);
