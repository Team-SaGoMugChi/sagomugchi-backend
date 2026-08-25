import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../core/media/audio_recorder_service.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/camera_self_view.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/video_call_widgets.dart';
import '../../application/diary_draft_provider.dart';

/// Screen 37 — Step 1. 실시간 말하기. Video-call style live recording — the
/// mic records for the whole call; ending the call stores the file path on
/// the diary draft (Phase 4 uploads it for analysis). → Step 1 처리 중.
class DiaryStep1LiveScreen extends ConsumerStatefulWidget {
  const DiaryStep1LiveScreen({super.key});

  @override
  ConsumerState<DiaryStep1LiveScreen> createState() =>
      _DiaryStep1LiveScreenState();
}

class _DiaryStep1LiveScreenState extends ConsumerState<DiaryStep1LiveScreen> {
  final _cameraKey = GlobalKey<CameraSelfViewState>();
  bool _micMuted = false;
  bool _speakerOff = false;

  @override
  void initState() {
    super.initState();
    ref
        .read(audioRecorderProvider)
        .start(
          fileName: 'diary_${DateFormatter.dateKey(DateTime.now())}_step1',
        );
  }

  /// 마이크 토글 = 녹음 일시정지/재개.
  Future<void> _toggleMic() async {
    final recorder = ref.read(audioRecorderProvider);
    if (_micMuted) {
      await recorder.resume();
    } else {
      await recorder.pause();
    }
    if (mounted) setState(() => _micMuted = !_micMuted);
  }

  Future<void> _endCall() async {
    // baseline 측정과 같은 순서: 정지 이미지 캡처를 녹음 정지보다 먼저 —
    // 녹음을 멈추는 사이 프레임이 바뀌는 걸 방지.
    final photo = await _cameraKey.currentState?.takePicture();
    if (photo != null) {
      ref.read(diaryDraftProvider.notifier).setFaceImagePath(photo.path);
    }

    final path = await ref.read(audioRecorderProvider).stop();
    if (path != null) {
      ref.read(diaryDraftProvider.notifier).setRecordingPath(path);
    }
    if (mounted) {
      context.pushReplacementNamed(AppRoute.diaryStep1Processing);
    }
  }

  @override
  Widget build(BuildContext context) {
    // autoDispose 프로바이더라 아무도 watch하지 않으면 start()~stop() 사이에
    // 폐기될 수 있다 — 이 화면이 살아있는 동안은 붙잡아 둔다.
    ref.watch(audioRecorderProvider);

    return Scaffold(
      backgroundColor: AppColors.callBackground,
      body: SafeArea(
        child: Column(
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(
                    Icons.arrow_back_ios_new_rounded,
                    size: 20,
                    color: AppColors.callTextPrimary,
                  ),
                  onPressed: () {
                    if (context.canPop()) context.pop();
                  },
                ),
                Expanded(
                  child: Text(
                    'Step 1. 말하기',
                    textAlign: TextAlign.center,
                    style: AppTypography.bodyLarge.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(
                    Icons.help_outline_rounded,
                    size: 20,
                    color: AppColors.callTextPrimary,
                  ),
                  onPressed: () => showHelpSheet(
                    context,
                    title: '말하기 도움말',
                    items: const [
                      '오늘 있었던 일을 통화하듯 편하게 이야기해주세요.',
                      '마이크 버튼으로 잠시 멈췄다가 이어 말할 수 있어요.',
                      '통화 종료를 누르면 녹음이 끝나고 분석이 시작돼요.',
                    ],
                  ),
                ),
              ],
            ),
            const CallStatusRow(label: 'AI와 실시간 대화 중'),
            Expanded(
              child: Stack(
                children: [
                  // TODO: 큰 상담 상대처럼 손 흔드는 포즈로 교체 예정
                  const Center(
                    child: MascotImage(
                      pose: MascotPose.waving,
                      size: 200,
                      onDark: true,
                    ),
                  ),
                  const Positioned(
                    top: 8,
                    left: AppSpacing.screenH,
                    child: CallChip(
                      icon: Icons.graphic_eq_rounded,
                      label: '음성 인식 중',
                    ),
                  ),
                  const Positioned(
                    top: 8,
                    right: AppSpacing.screenH,
                    child: CallAnalysisChip(),
                  ),
                  // 우상단(실시간 감정 분석 칩 아래) — 하단 버튼과 겹치지 않게.
                  Positioned(
                    top: 76,
                    right: AppSpacing.screenH,
                    child: CallUserPreview(cameraKey: _cameraKey),
                  ),
                  Positioned(
                    right: 0,
                    left: 0,
                    bottom: 16,
                    child: Center(
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CallControlButton(
                            icon: _micMuted
                                ? Icons.mic_off_rounded
                                : Icons.mic_rounded,
                            label: _micMuted ? '음소거 중' : '마이크',
                            onTap: _toggleMic,
                          ),
                          const SizedBox(width: 20),
                          CallControlButton(
                            icon: Icons.call_end_rounded,
                            label: '통화 종료',
                            danger: true,
                            onTap: _endCall,
                          ),
                          const SizedBox(width: 20),
                          CallControlButton(
                            icon: _speakerOff
                                ? Icons.volume_off_rounded
                                : Icons.volume_up_rounded,
                            label: '스피커',
                            onTap: () =>
                                setState(() => _speakerOff = !_speakerOff),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
