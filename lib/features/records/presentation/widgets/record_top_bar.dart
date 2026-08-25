import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';

/// Shared top bar for the written-day record screens (48–50): a back button
/// (exits to the written-day home), a centered title, and trailing actions
/// (notification + settings by default).
class RecordTopBar extends StatelessWidget {
  const RecordTopBar({super.key, required this.title, this.trailing});

  final String title;
  final List<Widget>? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: () => context.goNamed(AppRoute.homeWritten),
        ),
        Expanded(
          child: Text(title,
              textAlign: TextAlign.center, style: AppTypography.subtitle),
        ),
        ...(trailing ??
            [
              IconButton(
                icon: const Icon(Icons.notifications_none_rounded,
                    color: AppColors.textSecondary),
                onPressed: () => context.pushNamed(AppRoute.notifications),
              ),
              IconButton(
                icon: const Icon(Icons.settings_outlined,
                    color: AppColors.textSecondary),
                onPressed: () => context.pushNamed(AppRoute.settings),
              ),
            ]),
      ],
    );
  }
}
