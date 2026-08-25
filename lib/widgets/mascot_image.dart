import 'package:flutter/material.dart';

import '../core/constants/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Renders the mascot (탄카츄) in a given [pose].
///
/// Uses the real per-pose art from `assets/images/character/{pose}.png`
/// (2026-07-17 실장). Fallback chain: 포즈 이미지가 없으면 통합
/// 플레이스홀더([AppAssets.tankachuPlaceholder]), 그것도 없으면 스타일 박스.
class MascotImage extends StatelessWidget {
  const MascotImage({
    super.key,
    required this.pose,
    this.size = 120,
    this.onDark = false,
    this.alignment = Alignment.center,
  });

  final MascotPose pose;
  final double size;

  /// Use a lighter placeholder when shown on a dark (video-call) background.
  final bool onDark;

  /// 박스 안에서 이미지 정렬 (예: peeking 포즈는 bottomCenter로 손끝을
  /// 박스 하단에 딱 붙인다).
  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    // 원본이 크므로 표시 크기만큼만 디코드해 메모리를 아낀다.
    final cacheWidth =
        (size * MediaQuery.devicePixelRatioOf(context)).round();
    return Image.asset(
      AppAssets.mascot(pose),
      width: size,
      height: size,
      fit: BoxFit.contain,
      alignment: alignment,
      cacheWidth: cacheWidth,
      errorBuilder: (_, _, _) => Image.asset(
        AppAssets.tankachuPlaceholder,
        width: size,
        height: size,
        fit: BoxFit.contain,
        errorBuilder: (_, _, _) => _placeholder(),
      ),
    );
  }

  Widget _placeholder() {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: onDark ? AppColors.callSurface : AppColors.primarySoft,
        borderRadius: BorderRadius.circular(size * 0.26),
      ),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.pets_rounded,
            size: size * 0.34,
            color: onDark ? AppColors.callTextSecondary : AppColors.primary,
          ),
          SizedBox(height: size * 0.05),
          Text(
            pose.name,
            style: AppTypography.caption.copyWith(
              color: onDark ? AppColors.callTextSecondary : AppColors.primary,
              fontSize: size * 0.09,
            ),
          ),
        ],
      ),
    );
  }
}
