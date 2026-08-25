import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_assets.dart';
import '../../../../data/dummy/diary_flow_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_radius.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/mascot_image.dart';

/// Auxiliary — 숏폼 전체화면 플레이어. Full-screen player for the generated
/// short-form clip. The frame + controls mimic a real video player; play/pause
/// is a local toggle (no real playback yet).
class ShortformPlayerScreen extends StatefulWidget {
  const ShortformPlayerScreen({super.key});

  @override
  State<ShortformPlayerScreen> createState() => _ShortformPlayerScreenState();
}

class _ShortformPlayerScreenState extends State<ShortformPlayerScreen> {
  // Dummy playback position (00:03 of 01:32 ≈ 0.03).
  static const double _progress = 0.03;
  bool _playing = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.callBackground,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ── The "video" surface: the current frame, centered ──────────────
          // TODO: 실제 생성된 숏폼 영상 프레임으로 교체 예정
          const Center(
            child: MascotImage(pose: MascotPose.front, size: 200, onDark: true),
          ),

          // ── Bottom scrim so controls stay legible over the frame ──────────
          const Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            height: 220,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Colors.transparent, Color(0xCC000000)],
                ),
              ),
            ),
          ),

          // ── Center play / pause control ───────────────────────────────────
          Center(
            child: GestureDetector(
              onTap: () => setState(() => _playing = !_playing),
              child: Container(
                width: 72,
                height: 72,
                decoration: const BoxDecoration(
                  color: Color(0x55000000),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  _playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  size: 44,
                  color: Colors.white,
                ),
              ),
            ),
          ),

          // ── Top bar: back + title ─────────────────────────────────────────
          SafeArea(
            child: Row(
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
                const Expanded(
                  child: Text(
                    '숏폼 플레이어',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.callTextPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: 48),
              ],
            ),
          ),

          // ── Bottom controls: caption + scrubber + times ───────────────────
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.lg,
                  0,
                  AppSpacing.lg,
                  AppSpacing.lg,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '오늘의 이야기를 담은 영상',
                      style: TextStyle(
                        color: AppColors.callTextPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Gap.h12,
                    const _Scrubber(progress: _progress),
                    Gap.h8,
                    Row(
                      children: [
                        Text(
                          DiaryFlowDummy.videoPosition,
                          style: AppTypography.caption.copyWith(
                            color: AppColors.callTextPrimary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          DiaryFlowDummy.videoDuration,
                          style: AppTypography.caption.copyWith(
                            color: AppColors.callTextSecondary,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Icon(
                          Icons.fullscreen_rounded,
                          size: 18,
                          color: AppColors.callTextPrimary,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A static progress scrubber: filled track up to [progress] with a round thumb.
class _Scrubber extends StatelessWidget {
  const _Scrubber({required this.progress});
  final double progress;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 14,
      child: Stack(
        alignment: Alignment.centerLeft,
        children: [
          // Background track.
          Container(
            height: 4,
            decoration: BoxDecoration(
              color: Colors.white24,
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
          ),
          // Filled portion.
          FractionallySizedBox(
            widthFactor: progress,
            child: Container(
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(AppRadius.pill),
              ),
            ),
          ),
          // Thumb (centered on the playhead position).
          Align(
            alignment: Alignment(progress * 2 - 1, 0),
            child: Container(
              width: 14,
              height: 14,
              decoration: const BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
