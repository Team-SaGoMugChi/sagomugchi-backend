import 'package:flutter/material.dart';

import '../core/constants/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_typography.dart';
import 'mascot_image.dart';

/// A chat message bubble. Oddo messages sit on the left with a mascot avatar
/// and a white bubble; the user's sit on the right in a blue bubble. Shared by
/// the Step 2 follow-up chat and the counseling-record log.
class ChatBubble extends StatelessWidget {
  const ChatBubble({super.key, required this.fromOddo, required this.text});

  final bool fromOddo;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            fromOddo ? MainAxisAlignment.start : MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (fromOddo) ...[
            Container(
              width: 36,
              height: 36,
              decoration: const BoxDecoration(
                  color: AppColors.primarySoft, shape: BoxShape.circle),
              clipBehavior: Clip.antiAlias,
              // TODO: 프로필용 작은 정면 포즈로 교체 예정
              child: const MascotImage(pose: MascotPose.front, size: 36),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: fromOddo ? AppColors.surface : AppColors.primary,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(AppRadius.md),
                  topRight: const Radius.circular(AppRadius.md),
                  bottomLeft: Radius.circular(fromOddo ? 4 : AppRadius.md),
                  bottomRight: Radius.circular(fromOddo ? AppRadius.md : 4),
                ),
                border: fromOddo ? Border.all(color: AppColors.border) : null,
              ),
              child: Text(
                text,
                style: AppTypography.body.copyWith(
                    color: fromOddo
                        ? AppColors.textPrimary
                        : AppColors.textOnPrimary),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
