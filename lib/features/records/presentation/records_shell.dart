import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/app_routes.dart';
import '../../../widgets/diary_bottom_nav.dart';

/// Hosts the written-day context: the [일기][리포트][상담] tab bar wrapping the
/// three record screens (48–50). Each screen renders its own header (the
/// designs differ), so the shell only provides the bottom tab bar.
///
/// Built on go_router's [StatefulNavigationShell] so each tab keeps its own
/// navigation stack and scroll state.
class RecordsShell extends StatelessWidget {
  const RecordsShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: DiaryBottomNav(
        currentIndex: navigationShell.currentIndex,
        onSelect: (i) {
          // The 일기 tab returns to the written-day home (screenshot 1), not the
          // diary-detail branch. The detail screen is only reached via the
          // home's "작성한 일기 읽기" button.
          if (i == 0) {
            context.goNamed(AppRoute.homeWritten);
          } else {
            navigationShell.goBranch(
              i,
              initialLocation: i == navigationShell.currentIndex,
            );
          }
        },
      ),
    );
  }
}
