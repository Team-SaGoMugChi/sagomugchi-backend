import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'speech_to_text_service.dart';
import 'tts_service.dart';

/// One moment in a guided conversation — either 탄카츄 is speaking a prompt,
/// or it's waiting for the user's reply.
class ConversationTurn {
  const ConversationTurn({required this.caption, required this.speaking});

  final String caption;

  /// true while TTS is reading [caption]; false while listening for the
  /// user's answer (the caption is then an invitation like "편하게 말씀해주세요").
  final bool speaking;
}

/// Runs a scripted list of prompts as an actual back-and-forth: 탄카츄가 질문을
/// 읽고, 사용자가 대답하는 동안 기다렸다가(말이 멈추면 감지), 다음 질문으로
/// 넘어간다. STT는 내용을 이해하는 데 쓰지 않는다 — "말이 끝났다"는 신호로만
/// 쓴다(실제 답변 이해는 SFT 상담봇 영역, ROADMAP상 아직 미확정).
///
/// STT를 쓸 수 없는 기기/권한 거부 상태에서는 고정 시간만 기다렸다가 자동으로
/// 다음 질문으로 넘어가 대화가 멈추지 않는다.
class GuidedConversationController {
  GuidedConversationController(this._tts, this._stt);

  final TtsService _tts;
  final SpeechToTextService _stt;

  static const _fallbackReplyWindow = Duration(seconds: 6);
  // 4초 정도는 조용해야 "말이 끝났다"고 본다 — 이보다 짧으면 생각하며 말을
  // 잠깐 멈춘 것도 다음 질문으로 넘어가버려서 대답이 잘려버렸다(사용자 피드백).
  static const _silenceThreshold = Duration(seconds: 4);
  static const _maxTotal = Duration(seconds: 45);

  Future<void> run(
    List<String> prompts, {
    required void Function(ConversationTurn turn) onTurn,
  }) async {
    for (final prompt in prompts) {
      onTurn(ConversationTurn(caption: prompt, speaking: true));
      await _tts.speak(prompt);

      onTurn(const ConversationTurn(caption: '편하게 말씀해주세요.', speaking: false));
      await _stt.listenUntilPause(
        silenceThreshold: _silenceThreshold,
        maxTotal: _maxTotal,
        fallbackWait: _fallbackReplyWindow,
      );
    }
  }
}

/// Wires a fresh [TtsService] + [SpeechToTextService] pair for whichever
/// screen watches it — same autoDispose-tied-to-screen-lifetime shape as
/// the two services it composes.
final guidedConversationControllerProvider =
    Provider.autoDispose<GuidedConversationController>((ref) {
  return GuidedConversationController(
    ref.watch(ttsServiceProvider),
    ref.watch(speechToTextServiceProvider),
  );
});
