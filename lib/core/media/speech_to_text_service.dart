import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Detects when the user has finished talking — used to turn the baseline
/// guide from "읽어주는 대사"에서 실제 주고받는 대화처럼 느껴지게 만든다:
/// 질문을 읽고 → 사용자가 말하는 동안 기다렸다가 → 말이 끝나면(pause) 다음
/// 질문으로 넘어간다.
///
/// 여기서는 인식된 텍스트 자체는 쓰지 않는다(내용 이해는 SFT 상담봇 영역,
/// ROADMAP상 아직 미확정) — "말이 끝났다"는 신호만 이용한다.
class SpeechToTextService {
  final SpeechToText _stt = SpeechToText();
  bool _ready = false;
  bool _permanentError = false;

  Future<bool> _ensureReady() async {
    if (_ready) return true;
    try {
      _ready = await _stt.initialize(
        onError: (e) {
          if (e.permanent) _permanentError = true;
        },
      );
    } catch (_) {
      _ready = false;
    }
    return _ready;
  }

  /// 사용자가 말을 하다 잠깐 멈추는 것(생각하는 중)과 진짜 다 말한 것을
  /// 구분한다: 안드로이드 인식기 자체는 1~3초만 조용해도 세션을 끊어버릴 수
  /// 있어서(플랫폼 한계, pauseFor로 못 늘림), 세션이 끊겨도 그때까지 실제로
  /// 조용했던 시간이 [silenceThreshold]보다 짧으면 다시 듣기 시작한다. 즉
  /// "말이 끝났다"는 판정은 이 서비스가 직접, 세션 재시작을 넘나들며 잰다.
  ///
  /// 음성 인식 엔진이 없는 기기/권한 거부 상태에서는 대신 [fallbackWait]만큼만
  /// 기다린다 — 질문들이 텀 없이 연달아 재생되는 걸 막기 위한 안전장치.
  Future<void> listenUntilPause({
    Duration silenceThreshold = const Duration(seconds: 4),
    Duration maxTotal = const Duration(seconds: 45),
    Duration fallbackWait = const Duration(seconds: 6),
  }) async {
    if (!await _ensureReady()) {
      await Future.delayed(fallbackWait);
      return;
    }

    final deadline = DateTime.now().add(maxTotal);
    var lastSpeechAt = DateTime.now();

    while (DateTime.now().isBefore(deadline) && !_permanentError) {
      final remaining = deadline.difference(DateTime.now());
      await _listenOnce(
        pauseFor: silenceThreshold,
        listenFor: remaining,
        onSpeech: () => lastSpeechAt = DateTime.now(),
      );

      final quietFor = DateTime.now().difference(lastSpeechAt);
      if (quietFor >= silenceThreshold) return; // 진짜로 다 말했다.
      // 세션이 짧게 끊겼을 뿐 아직 침묵이 충분히 길지 않다 — 다시 듣는다.
      await Future.delayed(const Duration(milliseconds: 150));
    }
  }

  /// 한 번의 listen 세션. 상태가 "listening"을 벗어나면(pause 감지·타임아웃·
  /// 에러) 완료된다.
  Future<void> _listenOnce({
    required Duration pauseFor,
    required Duration listenFor,
    required void Function() onSpeech,
  }) async {
    if (listenFor <= Duration.zero) return;

    final done = Completer<void>();
    void finish() {
      if (!done.isCompleted) done.complete();
    }

    // listen() 호출 전에 걸어둬야 상태가 바뀌는 순간을 놓치지 않는다.
    _stt.statusListener = (status) {
      if (status != SpeechToText.listeningStatus) finish();
    };

    try {
      await _stt.listen(
        onResult: (result) {
          if (result.recognizedWords.trim().isNotEmpty) onSpeech();
        },
        onSoundLevelChange: (level) {
          // 인식은 못했어도 소리 자체가 크면(말하는 중) 침묵 타이머를 미룬다.
          if (level > 0) onSpeech();
        },
        listenOptions: SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          pauseFor: pauseFor,
          listenFor: listenFor,
          localeId: 'ko_KR',
        ),
      );
      unawaited(Future.delayed(listenFor + const Duration(seconds: 1), finish));
      await done.future;
    } catch (_) {
      finish();
    } finally {
      if (_stt.isListening) {
        await _stt.stop();
      }
    }
  }

  Future<void> stop() async {
    try {
      await _stt.stop();
    } catch (_) {}
  }

  Future<void> dispose() async {
    try {
      await _stt.cancel();
    } catch (_) {}
  }
}

final speechToTextServiceProvider = Provider.autoDispose<SpeechToTextService>((ref) {
  final service = SpeechToTextService();
  ref.onDispose(service.dispose);
  return service;
});
