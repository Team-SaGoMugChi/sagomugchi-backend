import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Live front-camera self view for the video-call style screens.
///
/// Handles the whole camera lifecycle and degrades gracefully: while
/// initializing, without permission, or on devices/tests without a camera it
/// shows [fallback] (defaults to the person-icon placeholder look).
class CameraSelfView extends StatefulWidget {
  const CameraSelfView({super.key, this.fallback});

  /// Shown when the preview isn't available. Defaults to a person icon on the
  /// call-surface color.
  final Widget? fallback;

  @override
  State<CameraSelfView> createState() => CameraSelfViewState();
}

/// Public so callers can grab a still frame via a `GlobalKey<CameraSelfViewState>`
/// (e.g. baseline 측정 종료 시 얼굴 사진 한 장 캡처).
class CameraSelfViewState extends State<CameraSelfView>
    with WidgetsBindingObserver {
  CameraController? _controller;

  /// 현재 프리뷰에서 정지 이미지 한 장을 캡처한다. 카메라가 준비되지 않았으면 null.
  Future<XFile?> takePicture() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) return null;
    if (controller.value.isTakingPicture) return null;
    try {
      return await controller.takePicture();
    } catch (_) {
      return null;
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _init();
  }

  Future<void> _init() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;
      final front = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        front,
        ResolutionPreset.low,
        enableAudio: false, // 녹음은 AudioRecorderService가 담당.
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _controller = controller);
    } catch (_) {
      // No camera / no permission / test environment → keep the fallback.
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Release the camera in background; re-init on resume (plugin guidance).
    final controller = _controller;
    if (controller == null) return;
    if (state == AppLifecycleState.inactive) {
      _controller = null;
      controller.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _init();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return widget.fallback ??
          Container(
            color: AppColors.callSurface,
            alignment: Alignment.center,
            child: const Icon(Icons.person_rounded,
                size: 34, color: AppColors.callTextSecondary),
          );
    }
    // Cover-fit the preview into whatever box the parent gives us.
    return LayoutBuilder(
      builder: (context, constraints) => ClipRect(
        child: FittedBox(
          fit: BoxFit.cover,
          clipBehavior: Clip.hardEdge,
          child: SizedBox(
            width: controller.value.previewSize?.height ?? constraints.maxWidth,
            height: controller.value.previewSize?.width ?? constraints.maxHeight,
            child: CameraPreview(controller),
          ),
        ),
      ),
    );
  }
}
