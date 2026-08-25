import 'dart:async';

import 'guided_conversation_controller.dart' show ConversationTurn;
import 'tts_service.dart';

export 'guided_conversation_controller.dart' show ConversationTurn;

/// 진짜 baseline 녹음 세션(하나의 [AudioRecorderService])의 진폭만으로
/// "말하는 중/멈춤"을 판단해서 [prompts]를 이어가는 대화 진행기.
///
/// [GuidedConversationController](튜토리얼 연습용)는 STT로 "말이 끝났다"를
/// 감지하는데, baseline 화면은 이미 그 녹음 자체가 진행 중이라 STT까지
/// 같이 마이크를 잡으면 녹음이 끊기거나 무음이 될 위험이 있다(코드 주석
/// 참고). 이 클래스는 그 녹음의 진폭 스트림만 재사용해서 같은 "자연스럽게
/// 기다렸다가 다음으로" 흐름을 마이크 충돌 없이 만든다.
///
/// [budget] 시간을 채우거나 [prompts]를 다 쓰면 멈춘다 — 실제로 얼마나
/// 오래 이야기하는지에 따라 몇 개 질문까지 갈지 자연스럽게 달라진다.
class AmplitudePacedConversationController {
  AmplitudePacedConversationController(this._tts, this._amplitude);

  final TtsService _tts;
  final Stream<double> _amplitude;

  // record 패키지의 dBFS 범위는 대략 -160(무음)~0(최대). 실기기 배경 잡음
  // 바닥을 감안해 -35dB를 "말하는 중" 문턱으로 잡았다(조용한 실내 기준
  // 실측 후 조정 가능 — 너무 낮으면 숨소리에도 반응, 너무 높으면 작은
  // 목소리를 놓친다).
  static const _voiceThreshold = -35.0;
  static const _silenceThreshold = Duration(seconds: 4);
  static const _startTalkingTimeout = Duration(seconds: 6);
  static const _maxPerPrompt = Duration(seconds: 40);

  bool _stopped = false;

  /// 화면이 먼저 종료되는 경우(스킵 버튼 등) 진행 중인 대기를 끊는다.
  void stop() => _stopped = true;

  Future<void> run(
    List<String> prompts, {
    required Duration budget,
    required void Function(ConversationTurn turn) onTurn,
  }) async {
    final elapsed = Stopwatch()..start();
    for (final prompt in prompts) {
      if (_stopped || elapsed.elapsed >= budget) break;
      onTurn(ConversationTurn(caption: prompt, speaking: true));
      await _tts.speak(prompt);
      if (_stopped) break;

      onTurn(const ConversationTurn(caption: '편하게 이야기해주세요.', speaking: false));
      await _waitForPause();
    }
  }

  /// 사용자가 말을 시작할 때까지 기다렸다가(문턱 이상 진폭 1회 감지),
  /// 그 뒤로 [_silenceThreshold] 동안 계속 조용해지면 반환한다. 아무도
  /// 말하지 않으면 [_startTalkingTimeout] 뒤에 그냥 다음으로 넘어가고,
  /// 너무 길게 말해도 [_maxPerPrompt]에서 강제로 끊는다.
  Future<void> _waitForPause() async {
    try {
      final startedTalking = await _amplitude
          .firstWhere((v) => v > _voiceThreshold)
          .timeout(_startTalkingTimeout)
          .then((_) => true)
          .catchError((_) => false);
      if (_stopped || !startedTalking) return;

      // 진폭 이벤트가 ~300ms마다 계속 들어오므로, 매 이벤트마다 마감을
      // 확인하는 것만으로 [_maxPerPrompt] 상한이 충분히 지켜진다.
      final deadline = DateTime.now().add(_maxPerPrompt);
      DateTime? silenceSince;
      await for (final v in _amplitude) {
        if (_stopped || DateTime.now().isAfter(deadline)) break;
        if (v <= _voiceThreshold) {
          silenceSince ??= DateTime.now();
          if (DateTime.now().difference(silenceSince) >= _silenceThreshold) {
            break;
          }
        } else {
          silenceSince = null;
        }
      }
    } catch (_) {
      // 진폭 스트림 문제(권한/기기) — 조용히 다음 질문으로 넘어간다.
    }
  }
}
