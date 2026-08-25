import 'package:flutter/material.dart';

import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';

/// A horizontal rule with a centered "또는" label, between the login button and
/// social-login options.
class OrDivider extends StatelessWidget {
  const OrDivider({super.key, this.label = '또는'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Expanded(child: Divider(color: AppColors.border)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(label, style: AppTypography.caption),
        ),
        const Expanded(child: Divider(color: AppColors.border)),
      ],
    );
  }
}
