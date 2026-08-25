import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Row tile: an icon in a soft circle, a title + optional description, and an
/// optional trailing widget (chevron / check / duration chip). Used by the
/// permission list, baseline checklist, and measurement-item lists.
class IconInfoTile extends StatelessWidget {
  const IconInfoTile({
    super.key,
    required this.icon,
    required this.title,
    this.description,
    this.trailing,
    this.iconColor = AppColors.primary,
    this.iconBackground = AppColors.primarySoft,
  });

  final IconData icon;
  final String title;
  final String? description;
  final Widget? trailing;
  final Color iconColor;
  final Color iconBackground;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: iconBackground,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 20, color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: AppTypography.body
                        .copyWith(fontWeight: FontWeight.w600)),
                if (description != null) ...[
                  const SizedBox(height: 2),
                  Text(description!, style: AppTypography.caption),
                ],
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 8),
            trailing!,
          ],
        ],
      ),
    );
  }
}
