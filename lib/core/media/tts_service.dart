import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// Speaks Korean guide prompts aloud for the video-call style screens
/// (튜토리얼 통화 연습, baseline 측정) — 탄카츄가 실제로 안내해주는 느낌을 준다.
///
/// Degrades silently: TTS 엔진이 없는 기기/테스트 환경에서도 화면이 죽지 않도록
/// 모든 실패를 조용히 삼킨다.
class TtsService {
  final FlutterTts _tts = FlutterTts()
    ..setLanguage('ko-KR')
    ..setSpeechRate(0.45)
    ..setPitch(1.05)
    ..awaitSpeakCompletion(true);

  /// [line] 하나를 읽고, 다 읽을 때까지 기다린다.
  Future<void> speak(String line) async {
    try {
      await _tts.speak(line);
    } catch (_) {
      // TTS unavailable — the on-screen caption still carries the guide.
    }
  }

  /// [lines]를 순서대로 읽는다. 각 줄이 끝날 때마다 [onLine]으로 알려줘서
  /// 화면이 현재 읽고 있는 문장을 자막처럼 보여줄 수 있게 한다.
  Future<void> speakSequence(
    List<String> lines, {
    void Function(String line)? onLine,
  }) async {
    for (final line in lines) {
      onLine?.call(line);
      await speak(line);
    }
  }

  Future<void> stop() async {
    try {
      await _tts.stop();
    } catch (_) {}
  }

  Future<void> dispose() async {
    try {
      await _tts.stop();
    } catch (_) {}
  }
}

/// One instance per consumer screen — screens start a sequence in initState
/// and stop it in dispose, same lifecycle shape as [AudioRecorderService].
final ttsServiceProvider = Provider.autoDispose<TtsService>((ref) {
  final service = TtsService();
  ref.onDispose(service.dispose);
  return service;
});
