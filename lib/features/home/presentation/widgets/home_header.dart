import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/oddo_wordmark.dart';

/// Home top bar: month selector + Oddo wordmark on the left, notification and
/// settings icons on the right.
class HomeHeader extends StatelessWidget {
  const HomeHeader({super.key, required this.month});

  final DateTime month;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              onTap: () => context.pushNamed(AppRoute.monthlyCalendar),
              child: Row(
                children: [
                  Text(DateFormatter.yearMonth(month),
                      style: AppTypography.bodySecondary),
                  const Icon(Icons.keyboard_arrow_down_rounded,
                      size: 18, color: AppColors.textSecondary),
                ],
              ),
            ),
            const SizedBox(height: 2),
            const OddoWordmark(fontSize: 28, withHeart: false),
          ],
        ),
        const Spacer(),
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
      ],
    );
  }
}
