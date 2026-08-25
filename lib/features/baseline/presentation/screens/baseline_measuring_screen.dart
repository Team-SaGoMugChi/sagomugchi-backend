import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/media/amplitude_paced_conversation_controller.dart';
import '../../../../core/media/audio_recorder_service.dart';
import '../../../../core/media/tts_service.dart';
import '../../../../data/dummy/baseline_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/camera_self_view.dart';
import '../../../../widgets/elapsed_timer_text.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/tip_card.dart';
import '../../application/baseline_face_image_provider.dart';
import '../../application/baseline_recording_provider.dart';
import '../widgets/baseline_header.dart';

/// Screen 19 — 얼굴·음성 Baseline 측정 중. Video-call style: live front camera
/// + mic recording (path kept for the Phase-4 analysis upload). Auto-advances
/// to the analysis screen after a dummy delay (tap the status bar to skip).
class BaselineMeasuringScreen extends ConsumerStatefulWidget {
  const BaselineMeasuringScreen({super.key});

  @override
  ConsumerState<BaselineMeasuringScreen> createState() =>
      _BaselineMeasuringScreenState();
}

class _BaselineMeasuringScreenState
    extends ConsumerState<BaselineMeasuringScreen> {
  final _cameraKey = GlobalKey<CameraSelfViewState>();
  bool _advanced = false;
  ConversationTurn? _turn;

  // 실제 baseline 음성 녹음이 화면 전체에서 계속 돌아가고 있어서, 여기서는
  // (튜토리얼 연습 화면과 달리) STT로 "말이 끝났는지"를 감지하지 않는다 —
  // 대신 그 녹음 자체의 진폭(AmplitudePacedConversationController)으로
  // "말하는 중/멈춤"을 판단해서 마이크를 두 번 잡지 않는다.
  //
  // 화면 안내 문구("5~7분")의 중간값을 목표 시간으로 잡는다 — 질문 목록을
  // 다 쓰기 전에 이 시간에 닿으면 자연스럽게 마무리한다. 실제로 얼마나
  // 오래 이야기하는지에 따라 몇 문항까지 갈지는 매번 달라진다.
  static const _budget = Duration(minutes: 6);

  AmplitudePacedConversationController? _conversation;

  @override
  void initState() {
    super.initState();
    _runGuideThenAdvance();
  }

  Future<void> _runGuideThenAdvance() async {
    final recorder = ref.read(audioRecorderProvider);
    // amplitudeStream()은 실제로 녹음 중일 때만 의미 있는 값을 준다 — 녹음이
    // 시작되기 전에 부르면 빈 스트림이라 매 질문이 대기 없이 그냥 넘어간다.
    await recorder.start(fileName: 'baseline_voice');
    if (!mounted || _advanced) return;
    final conversation = AmplitudePacedConversationController(
      ref.read(ttsServiceProvider),
      recorder.amplitudeStream(),
    );
    _conversation = conversation;
    await conversation.run(
      BaselineDummy.baselineConversationPrompts,
      budget: _budget,
      onTurn: (turn) {
        if (mounted) setState(() => _turn = turn);
      },
    );
    if (!mounted || _advanced) return;
    await ref.read(ttsServiceProvider).speak('감사합니다, 측정을 마칠게요.');
    await _advance();
  }

  @override
  void dispose() {
    // X 버튼 등으로 화면을 바로 나가면 _advance를 거치지 않으므로, 남아있는
    // 대화 대기 루프를 여기서 끊어준다.
    _conversation?.stop();
    super.dispose();
  }

  Future<void> _advance() async {
    if (_advanced || !mounted) return;
    _advanced = true;
    _conversation?.stop();

    // 정지 이미지 캡처는 녹음 정지보다 먼저 — 녹음을 멈추는 사이 프레임이 바뀌는 걸 방지.
    final photo = await _cameraKey.currentState?.takePicture();
    if (photo != null) {
      ref.read(baselineFaceImageProvider.notifier).set(photo.path);
    }

    final path = await ref.read(audioRecorderProvider).stop();
    if (path != null) {
      ref.read(baselineRecordingProvider.notifier).set(path);
    }
    if (mounted) context.pushReplacementNamed(AppRoute.baselineAnalyzing);
  }

  @override
  Widget build(BuildContext context) {
    // autoDispose 프로바이더라 아무도 watch하지 않으면 start()~stop() 사이에
    // 폐기될 수 있다 — 이 화면이 살아있는 동안은 붙잡아 둔다.
    ref.watch(audioRecorderProvider);
    ref.watch(ttsServiceProvider);

    return Scaffold(
      backgroundColor: AppColors.callBackground,
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: AppSpacing.sm),
              child: BaselineHeader(
                title: '베이스라인 측정 2/2',
                stepLabels: ['안내 진행', '측정 진행'],
                activeStep: 1,
                dark: true,
                leadingIcon: Icons.close_rounded,
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.md,
                  AppSpacing.screenH,
                  AppSpacing.md,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      '측정 중이에요!',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: AppColors.callTextPrimary,
                      ),
                    ),
                    Gap.h8,
                    const Text(
                      '얼굴 표정과 음성 데이터를 수집하고 있어요.\n잠시만 편안한 상태로 기다려주세요.',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppColors.callTextSecondary,
                      ),
                    ),
                    Gap.h16,
                    _PreviewCard(cameraKey: _cameraKey),
                    if (_turn != null) ...[
                      Gap.h12,
                      _GuideCaption(text: _turn!.caption),
                    ],
                    Gap.h24,
                    const Text(
                      '진행 상황',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppColors.callTextPrimary,
                      ),
                    ),
                    Gap.h12,
                    for (final p in BaselineDummy.measuringProgress) ...[
                      _ProgressRow(progress: p),
                      Gap.h16,
                    ],
                    const TipCard(
                      tips: BaselineDummy.measuringTips,
                      dark: true,
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.xs,
                AppSpacing.screenH,
                AppSpacing.xs,
              ),
              child: _StatusBar(onTap: _advance),
            ),
          ],
        ),
      ),
    );
  }
}

/// 탄카츄가 음성(TTS)으로 읽어주는 안내 문장의 자막 — 소리를 못 듣는 상황에서도
/// 무슨 말을 하라는 건지 알 수 있게 화면에 남겨둔다.
class _GuideCaption extends StatelessWidget {
  const _GuideCaption({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      decoration: const BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: AppRadius.card,
      ),
      child: Row(
        children: [
          const Icon(
            Icons.record_voice_over_rounded,
            size: 18,
            color: AppColors.primary,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              text,
              style: AppTypography.bodySecondary.copyWith(
                color: AppColors.callTextPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({required this.cameraKey});

  final GlobalKey<CameraSelfViewState> cameraKey;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 220,
      decoration: const BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: AppRadius.card,
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // 측정 대상인 사용자 본인 얼굴 — 전면 카메라 라이브 뷰.
          // (카메라 불가 시 마스코트 플레이스홀더로 폴백)
          CameraSelfView(
            key: cameraKey,
            fallback: const Center(
              // TODO: 손 흔드는 측정용 정면 포즈로 교체 예정 (character_sheet 10.인사)
              child: MascotImage(
                pose: MascotPose.waving,
                size: 150,
                onDark: true,
              ),
            ),
          ),
          const Positioned(top: 12, left: 12, child: _LiveChip()),
          const Positioned(top: 12, right: 12, child: _TimerChip()),
          const Positioned(bottom: 14, right: 14, child: _Waveform()),
        ],
      ),
    );
  }
}

class _LiveChip extends StatelessWidget {
  const _LiveChip();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.callBackground,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: const BoxDecoration(
              color: AppColors.error,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 5),
          Text(
            'LIVE',
            style: AppTypography.caption.copyWith(
              color: AppColors.callTextPrimary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _TimerChip extends StatelessWidget {
  const _TimerChip();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.callBackground,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.schedule_rounded,
            size: 13,
            color: AppColors.callTextSecondary,
          ),
          const SizedBox(width: 4),
          // 측정 시작부터 실제 경과 시간.
          ElapsedTimerText(
            showHours: false,
            style: AppTypography.caption.copyWith(
              color: AppColors.callTextPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _Waveform extends StatelessWidget {
  const _Waveform();

  static const List<double> _bars = [10, 18, 8, 22, 14, 26, 12, 20];

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        for (final h in _bars)
          Container(
            width: 3,
            height: h,
            margin: const EdgeInsets.symmetric(horizontal: 1.5),
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
      ],
    );
  }
}

class _ProgressRow extends StatelessWidget {
  const _ProgressRow({required this.progress});
  final MeasureProgress progress;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              progress.label,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.callTextPrimary,
              ),
            ),
            const Spacer(),
            Text(
              '${(progress.value * 100).round()}%',
              style: AppTypography.bodySecondary.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: LinearProgressIndicator(
            value: progress.value,
            minHeight: 8,
            backgroundColor: AppColors.callSurface,
            valueColor: const AlwaysStoppedAnimation(AppColors.primary),
          ),
        ),
      ],
    );
  }
}

class _StatusBar extends StatelessWidget {
  const _StatusBar({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.callSurface,
      borderRadius: AppRadius.button,
      child: InkWell(
        borderRadius: AppRadius.button,
        onTap: onTap,
        child: Container(
          height: 56,
          alignment: Alignment.center,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.callTextSecondary,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '측정 중... 잠시만 기다려주세요',
                style: AppTypography.button.copyWith(
                  color: AppColors.callTextSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
