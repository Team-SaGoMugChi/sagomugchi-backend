import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// Small shield-icon + caption note about data safety, used in form footers.
class SecurityNote extends StatelessWidget {
  const SecurityNote({super.key, required this.text, this.center = false});

  final String text;
  final bool center;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment:
          center ? MainAxisAlignment.center : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.verified_user_outlined,
            size: 14, color: AppColors.textTertiary),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            text,
            textAlign: center ? TextAlign.center : TextAlign.start,
            style: AppTypography.caption,
          ),
        ),
      ],
    );
  }
}
