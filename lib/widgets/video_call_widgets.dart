import 'dart:math';

import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_typography.dart';
import 'camera_self_view.dart';
import 'elapsed_timer_text.dart';

/// Shared chrome for the dark video-call screens (tutorial call practice,
/// baseline measuring, Step 1 live speaking, Step 4 counseling). Extracted so
/// the four screens share one implementation.

/// Live status row: a colored dot + label + live elapsed timer, centered.
class CallStatusRow extends StatelessWidget {
  const CallStatusRow({
    super.key,
    required this.label,
    this.dotColor = AppColors.error,
  });

  final String label;
  final Color dotColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: AppTypography.caption.copyWith(
            color: AppColors.callTextSecondary,
          ),
        ),
        const SizedBox(width: 10),
        // 화면 진입부터 실제로 흐르는 경과 시간.
        ElapsedTimerText(
          style: AppTypography.caption.copyWith(
            color: AppColors.callTextPrimary,
          ),
        ),
      ],
    );
  }
}

/// Small pill chip on the dark call surface (e.g. "음성 인식 중").
class CallChip extends StatelessWidget {
  const CallChip({super.key, required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: AppColors.primary),
          const SizedBox(width: 5),
          Text(
            label,
            style: AppTypography.caption.copyWith(
              color: AppColors.callTextPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

/// "실시간 감정 분석" chip with a live-animated waveform — the shared analysis
/// indicator for the call screens (Step 1 말하기 / Step 4 상담). The bars pulse
/// continuously so measurement visibly looks in progress.
class CallAnalysisChip extends StatefulWidget {
  const CallAnalysisChip({super.key, this.label = '실시간 감정 분석'});

  final String label;

  @override
  State<CallAnalysisChip> createState() => _CallAnalysisChipState();
}

class _CallAnalysisChipState extends State<CallAnalysisChip>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  /// Per-bar base heights — the waveform silhouette the pulse plays around.
  static const List<double> _bases = [6, 12, 8, 16, 10, 14, 7];

  /// Fixed lane height = tallest base + pulse amplitude, so the chip's gray
  /// box never resizes while the bars move inside it.
  static const double _amplitude = 4;
  static const double _laneHeight = 20; // max(_bases)=16 + _amplitude

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.label,
            style: AppTypography.caption.copyWith(
              color: AppColors.callTextSecondary,
            ),
          ),
          const SizedBox(height: 4),
          SizedBox(
            height: _laneHeight,
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                final t = _controller.value * 2 * pi;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    for (var i = 0; i < _bases.length; i++)
                      Container(
                        width: 3,
                        // 막대마다 위상을 다르게 준 사인파 → 파동이 흐르는
                        // 느낌. 고정 높이 레인 안에서 중앙 기준으로만 신축.
                        height: (_bases[i] + _amplitude * sin(t + i * 0.9))
                            .clamp(2.0, _laneHeight),
                        margin: const EdgeInsets.symmetric(horizontal: 1),
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Small user-camera self view (bottom-left of the call view). Shows the live
/// front camera; falls back to the person-icon placeholder without one.
class CallUserPreview extends StatelessWidget {
  const CallUserPreview({
    super.key,
    this.width = 84,
    this.height = 112,
    this.cameraKey,
  });

  final double width;
  final double height;

  /// 통화 종료 시 정지 이미지 한 장을 캡처해야 하는 화면(Step1 말하기 등)이
  /// 내부 [CameraSelfView]에 접근할 수 있게 넘기는 키.
  final GlobalKey<CameraSelfViewState>? cameraKey;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: AppColors.callSurface,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      clipBehavior: Clip.antiAlias,
      child: CameraSelfView(key: cameraKey),
    );
  }
}

/// A round call-control button (mic / end / speaker …) with an optional label.
class CallControlButton extends StatelessWidget {
  const CallControlButton({
    super.key,
    required this.icon,
    this.label,
    this.danger = false,
    this.onTap,
  });

  final IconData icon;
  final String? label;
  final bool danger;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final button = GestureDetector(
      onTap: onTap,
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          color: danger ? AppColors.error : AppColors.callSurface,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 24, color: AppColors.callTextPrimary),
      ),
    );

    if (label == null) return button;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        button,
        const SizedBox(height: 6),
        Text(
          label!,
          style: AppTypography.caption.copyWith(
            color: AppColors.callTextSecondary,
          ),
        ),
      ],
    );
  }
}
