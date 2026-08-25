import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// The three tabs of the written-day context.
enum DiaryTab { diary, report, counsel }

/// Bottom tab bar shown only in the written-day context: [일기][리포트][상담].
/// Driven by the records [StatefulNavigationShell] in the router.
class DiaryBottomNav extends StatelessWidget {
  const DiaryBottomNav({
    super.key,
    required this.currentIndex,
    required this.onSelect,
  });

  final int currentIndex;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return BottomNavigationBar(
      currentIndex: currentIndex,
      onTap: onSelect,
      type: BottomNavigationBarType.fixed,
      backgroundColor: AppColors.background,
      selectedItemColor: AppColors.primary,
      unselectedItemColor: AppColors.inactive,
      showUnselectedLabels: true,
      elevation: 0,
      items: const [
        BottomNavigationBarItem(
          icon: Icon(Icons.menu_book_rounded),
          label: '일기',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.insights_rounded),
          label: '리포트',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.chat_bubble_rounded),
          label: '상담',
        ),
      ],
    );
  }
}
