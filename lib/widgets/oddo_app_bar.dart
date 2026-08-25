import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme/app_colors.dart';

/// Standard header: optional back button / title / optional trailing actions
/// (help or settings). Most internal screens use this.
class OddoAppBar extends StatelessWidget implements PreferredSizeWidget {
  const OddoAppBar({
    super.key,
    this.title,
    this.showBack = true,
    this.onBack,
    this.actions,
    this.backgroundColor = AppColors.background,
    this.foregroundColor = AppColors.textStrong,
  });

  final String? title;
  final bool showBack;
  final VoidCallback? onBack;
  final List<Widget>? actions;
  final Color backgroundColor;
  final Color foregroundColor;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: backgroundColor,
      foregroundColor: foregroundColor,
      title: title != null ? Text(title!) : null,
      leading: showBack
          ? IconButton(
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
              onPressed: onBack ??
                  () {
                    if (context.canPop()) context.pop();
                  },
            )
          : null,
      automaticallyImplyLeading: false,
      actions: actions,
    );
  }
}
