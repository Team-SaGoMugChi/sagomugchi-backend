import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/diary_flow_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/help_sheet.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/video_call_widgets.dart';

/// Screen 44 — Step 4. 영상통화 상담. Video-call style counseling. 상담 종료 →
/// 리포트 생성.
class DiaryStep4CounselCallScreen extends StatefulWidget {
  const DiaryStep4CounselCallScreen({super.key});

  @override
  State<DiaryStep4CounselCallScreen> createState() =>
      _DiaryStep4CounselCallScreenState();
}

class _DiaryStep4CounselCallScreenState
    extends State<DiaryStep4CounselCallScreen> {
  // 시각 상태 토글 — 실제 오디오 입출력은 Phase 5(상담봇 음성)에서 연결.
  bool _micMuted = false;
  bool _speakerOff = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.callBackground,
      body: SafeArea(
        child: Column(
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.close_rounded,
                      color: AppColors.callTextPrimary),
                  onPressed: () {
                    if (context.canPop()) context.pop();
                  },
                ),
                const Expanded(
                  child: Text('Step 4. 상담하기',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.callTextPrimary)),
                ),
                IconButton(
                  icon: const Icon(Icons.help_outline_rounded,
                      color: AppColors.callTextPrimary),
                  onPressed: () => showHelpSheet(
                    context,
                    title: '상담하기 도움말',
                    items: const [
                      '탄카츄가 오늘의 감정을 함께 돌아봐줘요.',
                      '떠오르는 대로 편하게 답하면 돼요. 정답은 없어요.',
                      '상담 종료를 누르면 감정 리포트가 만들어져요.',
                    ],
                  ),
                ),
              ],
            ),
            const CallStatusRow(
              label: DiaryFlowDummy.counselStatus,
              dotColor: AppColors.success,
            ),
            Expanded(
              child: Stack(
                children: [
                  // TODO: 상담사처럼 차분하고 공감하는 큰 포즈로 교체 예정
                  const Center(
                      child: MascotImage(
                          pose: MascotPose.counselor, size: 200, onDark: true)),
                  // Step1과 동일한 실시간 분석 인디케이터로 통일.
                  const Positioned(
                    top: 8,
                    right: AppSpacing.screenH,
                    child: CallAnalysisChip(),
                  ),
                  // 우상단(실시간 감정 분석 칩 아래) — 자막 말풍선과 겹치지 않게.
                  const Positioned(
                      top: 76,
                      right: AppSpacing.screenH,
                      child: CallUserPreview(width: 80, height: 106)),
                  // 컨트롤 버튼줄(아이콘 56 + 라벨 ≈ 92px) 위로 띄워 겹침 방지.
                  const Positioned(
                    left: AppSpacing.screenH,
                    right: AppSpacing.screenH,
                    bottom: 108,
                    child: _OddoBubble(),
                  ),
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 12,
                    child: Center(
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CallControlButton(
                            icon: _micMuted
                                ? Icons.mic_off_rounded
                                : Icons.mic_rounded,
                            label: _micMuted ? '음소거 중' : '마이크',
                            onTap: () =>
                                setState(() => _micMuted = !_micMuted),
                          ),
                          const SizedBox(width: 20),
                          CallControlButton(
                            icon: Icons.call_end_rounded,
                            label: '상담 종료',
                            danger: true,
                            onTap: () => context
                                .pushReplacementNamed(AppRoute.reportGenerating),
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

class _OddoBubble extends StatelessWidget {
  const _OddoBubble();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Text(DiaryFlowDummy.counselBubble,
          style: AppTypography.bodySecondary
              .copyWith(color: AppColors.textPrimary)),
    );
  }
}
