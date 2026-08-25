import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

/// Microphone recording for the speaking screens (baseline 측정, Step 1
/// 말하기). Records WAV into the temp directory and hands back the file
/// path — Phase 4 uploads that file to the AI server for analysis.
///
/// WAV(PCM)를 쓰는 이유: AI 서버의 librosa/soundfile이 m4a(AAC)를 디코딩하지
/// 못한다(서버 환경에 ffmpeg가 없어 `Format not recognised` 에러) — soundfile이
/// 바로 읽을 수 있는 포맷이어야 한다.
///
/// Degrades silently: without permission (or in tests) [start] returns false
/// and [stop] returns null, so screens keep working as pure UI.
class AudioRecorderService {
  final AudioRecorder _recorder = AudioRecorder();

  bool _recording = false;

  bool get isRecording => _recording;

  /// Starts recording into `<tmp>/<fileName>.wav`. False when unavailable.
  Future<bool> start({required String fileName}) async {
    try {
      if (_recording || !await _recorder.hasPermission()) return false;
      final dir = await getTemporaryDirectory();
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.wav),
        path: '${dir.path}/$fileName.wav',
      );
      _recording = true;
      return true;
    } catch (_) {
      return false;
    }
  }

  /// 녹음 일시정지 (마이크 음소거 버튼용). 실패는 조용히 무시.
  Future<void> pause() async {
    if (!_recording) return;
    try {
      await _recorder.pause();
    } catch (_) {}
  }

  /// 일시정지된 녹음 재개.
  Future<void> resume() async {
    if (!_recording) return;
    try {
      await _recorder.resume();
    } catch (_) {}
  }

  /// dBFS 진폭 스트림(대략 -160=무음 ~ 0=최대) — 별도 STT 엔진 없이 "지금
  /// 말하는 중인지"를 판단하는 데 쓴다. baseline 녹음 세션 자체의 진폭을
  /// 재사용하므로 마이크를 두 번 잡지 않는다(STT를 동시에 쓰면 baseline
  /// 녹음 파일이 끊기던 문제의 근본 해결책).
  ///
  /// 녹음 중이 아니면(권한 거부, 테스트 환경 등) 빈 스트림을 준다 — record
  /// 패키지는 [AudioRecorder.onAmplitudeChanged]를 호출하는 순간 실제
  /// 녹음 여부와 무관하게 주기적 타이머를 내부에서 시작해버려서, 안 쓸
  /// 스트림을 만들어두기만 해도 타이머가 계속 도는(위젯 테스트에서 "pending
  /// timer"로 잡히는) 문제가 있었다.
  Stream<double> amplitudeStream({
    Duration interval = const Duration(milliseconds: 300),
  }) {
    if (!_recording) return const Stream.empty();
    return _recorder
        .onAmplitudeChanged(interval)
        .map((a) => a.current)
        .handleError((_) {});
  }

  /// Stops and returns the recorded file's path (null when nothing recorded).
  Future<String?> stop() async {
    if (!_recording) return null;
    _recording = false;
    try {
      return await _recorder.stop();
    } catch (_) {
      return null;
    }
  }

  Future<void> dispose() async {
    try {
      await _recorder.dispose();
    } catch (_) {
      // Platform channel unavailable (tests) — nothing to release.
    }
  }
}

/// One recorder per consumer — screens read this and manage start/stop within
/// their own lifecycle.
final audioRecorderProvider = Provider.autoDispose<AudioRecorderService>((ref) {
  final service = AudioRecorderService();
  ref.onDispose(service.dispose);
  return service;
});
