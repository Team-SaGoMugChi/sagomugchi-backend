import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rive/rive.dart' as rive;

import '../core/constants/app_assets.dart';
import '../core/media/guided_conversation_controller.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'mascot_image.dart';

/// 탄카츄가 [lines]를 실제 대화처럼 진행한다: 한 줄을 음성(TTS)으로 읽고 →
/// 사용자가 대답하는 동안 기다렸다가(말이 멈추면 STT로 감지) → 다음 줄로
/// 넘어간다. 말하는 동안과 듣는 동안 서로 다른 애니메이션으로 지금 통화의
/// 어느 쪽 차례인지 보여준다.
///
/// 입 모양은 `assets/animations/README.md` 스펙의 Rive 리깅 애니메이션이
/// 있으면 그걸 쓰고(제대로 된 애니메이션 — 장기 목표), 아직 없으면(현재
/// 상태) 정지 이미지 위에 얹는 절차적 연출로 조용히 폴백한다. 즉 그 `.riv`
/// 파일을 넣기만 하면 이 파일은 손댈 필요 없이 자동으로 업그레이드된다.
///
/// 화면 진입 시 자동으로 시작하고, 화면을 벗어나면(dispose) 중단된다. TTS/STT가
/// 없는 기기에서도 자막과 고정 대기시간으로 대화가 계속 진행된다.
class TalkingMascotGuide extends ConsumerStatefulWidget {
  const TalkingMascotGuide({
    super.key,
    required this.lines,
    // mic 포즈는 마이크 소품이 입 바로 앞을 가려서 입 모양 애니메이션과
    // 겹친다 — waving 포즈가 얼굴이 트여 있어 입이 그대로 보인다
    // (TANKACHU_POSES.md 11번 화면 지정 포즈이기도 함).
    this.pose = MascotPose.waving,
    this.size = 190,
  });

  final List<String> lines;
  final MascotPose pose;
  final double size;

  @override
  ConsumerState<TalkingMascotGuide> createState() => _TalkingMascotGuideState();
}

class _TalkingMascotGuideState extends ConsumerState<TalkingMascotGuide>
    with TickerProviderStateMixin {
  // 말하는 동안 켜지는 은은한 링/이퀄라이저 박자 — 몸 전체를 흔들던 이전
  // 버전은 "떨림"으로 보인다는 피드백을 받아, 이제 몸은 거의 가만히 두고
  // 이 박자는 링·이퀄라이저 바에만 쓴다(입 모양은 별도 _mouthFlap이 담당).
  late final AnimationController _speakBeat = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 520),
  )..repeat();

  // 입을 벌렸다 오므렸다 하는 빠른 박자 — 서로 다른 두 주기를 합쳐서 음절
  // 단위로 불규칙하게 움직이는 것처럼 보이게 한다(순수 사인파는 기계적으로
  // 보인다는 게 실제로 확인됨).
  late final AnimationController _mouthFlap = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 170),
  )..repeat();
  late final AnimationController _mouthFlap2 = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 260),
  )..repeat();

  // 항상 도는 느린 숨쉬기 애니메이션 — 정지 화면처럼 안 보이게.
  late final AnimationController _idleBreath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);

  // 듣는 동안 마스코트 주변에 번지는 링 — "지금 네 차례야"를 보여주는 신호.
  late final AnimationController _listenRing = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  ConversationTurn? _turn;

  // assets/animations/README.md에 적힌 계약 — 아티스트가 이 이름으로 만든
  // .riv를 넣으면 아래에서 자동으로 로드해서 쓴다.
  static const _riveAssetPath = 'assets/animations/tankachu_talk.riv';
  static const _riveStateMachineName = 'Talk';
  static const _riveSpeakingInputName = 'speaking';

  rive.File? _riveFile;
  rive.RiveWidgetController? _riveController;
  rive.BooleanInput? _riveSpeakingInput;

  @override
  void initState() {
    super.initState();
    Future.microtask(_run);
    Future.microtask(_tryLoadRive);
  }

  Future<void> _run() async {
    if (widget.lines.isEmpty || !mounted) return;
    await ref
        .read(guidedConversationControllerProvider)
        .run(
          widget.lines,
          onTurn: (turn) {
            if (mounted) setState(() => _turn = turn);
            _riveSpeakingInput?.value = turn.speaking;
          },
        );
    if (mounted) setState(() => _turn = null);
    _riveSpeakingInput?.value = false;
  }

  /// .riv 애셋이 아직 없거나(현재) 로드가 실패하면 조용히 실패해서 기존
  /// 절차적 입 애니메이션으로 남는다 — 이 위젯을 쓰는 화면들은 신경 쓸 필요
  /// 없이 애셋이 생기는 순간 자동으로 업그레이드된다.
  Future<void> _tryLoadRive() async {
    try {
      final file = await rive.File.asset(
        _riveAssetPath,
        riveFactory: rive.Factory.rive,
      );
      if (file == null || !mounted) {
        file?.dispose();
        return;
      }
      final controller = rive.RiveWidgetController(
        file,
        stateMachineSelector: rive.StateMachineSelector.byName(
          _riveStateMachineName,
        ),
      );
      // state machine input 대신 Data Binding을 쓰라는 게 최신 권장이지만,
      // 그러려면 Rive 파일 쪽에 View Model 바인딩까지 잡혀 있어야 해서
      // 애셋 만드는 사람 입장에서 훨씬 손이 많이 간다 — boolean input이
      // 훨씬 단순해서 지금은 이쪽으로 계약을 잡았다.
      final stateMachine = controller.stateMachine;
      // ignore: deprecated_member_use
      final speakingInput = stateMachine.boolean(_riveSpeakingInputName);
      if (!mounted) {
        controller.dispose();
        file.dispose();
        return;
      }
      setState(() {
        _riveFile = file;
        _riveController = controller;
        _riveSpeakingInput = speakingInput;
      });
    } catch (_) {
      // 폴백: 절차적 입 애니메이션 그대로 사용.
    }
  }

  @override
  void dispose() {
    _speakBeat.dispose();
    _mouthFlap.dispose();
    _mouthFlap2.dispose();
    _idleBreath.dispose();
    _listenRing.dispose();
    _riveController?.dispose();
    _riveFile?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // autoDispose 서비스 체인(TTS+STT)이 이 화면이 떠 있는 동안 계속 살아있게
    // 붙잡아 둔다 (녹음 서비스에서 겪었던 것과 같은 종류의 버그를 막기 위함).
    ref.watch(guidedConversationControllerProvider);

    final speaking = _turn?.speaking ?? false;
    final listening = _turn != null && !speaking;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: widget.size * 1.35,
          height: widget.size * 1.35,
          child: Stack(
            alignment: Alignment.center,
            children: [
              if (listening)
                AnimatedBuilder(
                  animation: _listenRing,
                  builder: (context, _) {
                    final t = _listenRing.value;
                    return Container(
                      width: widget.size * (1.05 + t * 0.3),
                      height: widget.size * (1.05 + t * 0.3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: AppColors.primary.withValues(alpha: 1 - t),
                          width: 2,
                        ),
                      ),
                    );
                  },
                ),
              // 말하는 동안 켜지는 고정 링 — 영상통화에서 "지금 소리 내는 쪽"을
              // 테두리로 표시하는 것과 같은 언어. 은은하게 맥동한다.
              if (speaking)
                AnimatedBuilder(
                  animation: _speakBeat,
                  builder: (context, _) {
                    final pulse = 0.5 + 0.5 * sin(_speakBeat.value * 2 * pi);
                    return Container(
                      width: widget.size * 1.14,
                      height: widget.size * 1.14,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: AppColors.primary.withValues(
                            alpha: 0.35 + pulse * 0.35,
                          ),
                          width: 3,
                        ),
                      ),
                    );
                  },
                ),
              AnimatedBuilder(
                animation: _idleBreath,
                builder: (context, child) {
                  // 몸 전체를 흔들던 이전 버전(bob+rotation+scale)은 "떨림"으로
                  // 보인다는 피드백을 받았다 — 이제 몸은 숨쉬기 정도만 움직이고,
                  // "말하는 중"이라는 인상은 아래 입 모양 애니메이션이 낸다.
                  final breath = sin(_idleBreath.value * pi) * 0.012;
                  return Transform.scale(scale: 1.0 + breath, child: child);
                },
                child: SizedBox(
                  width: widget.size,
                  height: widget.size,
                  child: _riveController != null
                      ? rive.RiveWidget(
                          controller: _riveController!,
                          fit: rive.Fit.contain,
                        )
                      : Stack(
                          alignment: Alignment.center,
                          children: [
                            MascotImage(
                              pose: widget.pose,
                              size: widget.size,
                              onDark: true,
                            ),
                            // 코 바로 아래 입 자리(waving.png 실측 좌표 기준
                            // 보정) — speaking일 때만 벌렸다 오므렸다 해서
                            // 말하는 것처럼 보이게(Rive 애셋 준비 전 폴백).
                            Align(
                              alignment: const Alignment(0.03, 0.02),
                              child: _MouthFlap(
                                speaking: speaking,
                                beat1: _mouthFlap,
                                beat2: _mouthFlap2,
                                baseWidth: widget.size * 0.068,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
              if (speaking)
                Positioned(
                  bottom: widget.size * 0.06,
                  child: _SpeakingWaveform(animation: _speakBeat),
                ),
            ],
          ),
        ),
        if (_turn != null) ...[
          Gap.h8,
          Container(
            constraints: const BoxConstraints(maxWidth: 280),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            decoration: const BoxDecoration(
              color: AppColors.callSurface,
              borderRadius: AppRadius.card,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  listening
                      ? Icons.mic_rounded
                      : Icons.record_voice_over_rounded,
                  size: 16,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    _turn!.caption,
                    textAlign: TextAlign.center,
                    style: AppTypography.bodySecondary.copyWith(
                      color: AppColors.callTextPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

/// 코 바로 아래 정적인 "y" 모양 입 위에 겹쳐 그리는 작은 타원 — speaking일
/// 때 두 개의 서로 다른 주기(_beat1/_beat2)를 합쳐 벌렸다 오므렸다 해서 음절
/// 단위로 불규칙하게 말하는 것처럼 보이게 한다. 색은 원본 아트의 입 선
/// 색(waving.png 실측)에 맞춰서 안 벌어져 있을 때는 정적 아트와 거의
/// 구분되지 않게 자연스럽게 겹친다.
class _MouthFlap extends StatelessWidget {
  const _MouthFlap({
    required this.speaking,
    required this.beat1,
    required this.beat2,
    required this.baseWidth,
  });

  final bool speaking;
  final Animation<double> beat1;
  final Animation<double> beat2;
  final double baseWidth;

  static const _mouthColor = Color(0xFF3F2C17);

  @override
  Widget build(BuildContext context) {
    if (!speaking) {
      return SizedBox(width: baseWidth, height: baseWidth * 0.28);
    }
    return AnimatedBuilder(
      animation: Listenable.merge([beat1, beat2]),
      builder: (context, _) {
        final open =
            (sin(beat1.value * 2 * pi) * 0.6 +
                        sin(beat2.value * 2 * pi + 0.7) * 0.4)
                    .clamp(-1.0, 1.0) *
                0.5 +
            0.5;
        final height = baseWidth * (0.3 + open * 0.75);
        return Container(
          width: baseWidth,
          height: height,
          decoration: BoxDecoration(
            color: _mouthColor,
            borderRadius: BorderRadius.circular(baseWidth),
          ),
        );
      },
    );
  }
}

/// 마스코트 턱 아래에 붙는 작은 사운드 바 — "지금 입에서 소리가 나고 있다"는
/// 걸 트랜스폼 애니메이션보다 훨씬 명확하게 전달하는 시각 언어(통화 앱들이
/// 흔히 쓰는 활성 스피커 표시와 같은 방식).
class _SpeakingWaveform extends StatelessWidget {
  const _SpeakingWaveform({required this.animation});

  final Animation<double> animation;

  static const List<double> _bases = [5, 10, 7, 12, 6];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: AnimatedBuilder(
        animation: animation,
        builder: (context, _) {
          final t = animation.value * 2 * pi;
          return Row(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              for (var i = 0; i < _bases.length; i++)
                Container(
                  width: 3,
                  height: (_bases[i] + 5 * sin(t * 1.6 + i * 1.1).abs()).clamp(
                    3.0,
                    16.0,
                  ),
                  margin: const EdgeInsets.symmetric(horizontal: 1.5),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
