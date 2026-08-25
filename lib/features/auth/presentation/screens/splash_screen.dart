import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../core/constants/app_assets.dart';
import '../../../../features/auth/application/auth_controller.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/mascot_image.dart';
import '../../../../widgets/oddo_wordmark.dart';

/// Screen 1 — 스플래시. Shows the brand while restoring the saved session,
/// then routes to home (auto-login) or the login screen.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    // Restore the session while the brand moment plays (min splash time).
    final results = await Future.wait<Object?>([
      Future<void>.delayed(const Duration(milliseconds: 1500)),
      ref.read(authControllerProvider.notifier).restoreSession(),
    ]);
    if (!mounted) return;
    final loggedIn = results[1] != null;
    context.goNamed(loggedIn ? AppRoute.home : AppRoute.login);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AppBackground(
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const Spacer(flex: 2),
              const OddoWordmark(fontSize: 56),
              Gap.h20,
              Text(
                '오늘의 마음을\n함께 기록해요',
                textAlign: TextAlign.center,
                style: AppTypography.bodyLarge
                    .copyWith(color: AppColors.textSecondary),
              ),
              Gap.h24,
              // TODO: 환영하며 손 흔드는 정면 포즈로 교체 예정 (character_sheet 10.인사하는 모습)
              const MascotImage(pose: MascotPose.waving, size: 200),
              const Spacer(flex: 3),
              const _LoadingDots(),
              Gap.h32,
            ],
          ),
        ),
      ),
    );
  }
}

class _LoadingDots extends StatelessWidget {
  const _LoadingDots();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < 3; i++)
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 4),
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i == 0 ? AppColors.primary : AppColors.primarySoftBorder,
            ),
          ),
      ],
    );
  }
}
