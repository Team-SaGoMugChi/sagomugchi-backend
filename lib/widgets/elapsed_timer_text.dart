import 'dart:async';

import 'package:flutter/material.dart';

/// 화면 진입 시점부터 흐르는 경과 시간 텍스트 (1초 갱신).
/// 통화형 화면의 상태줄·측정 타이머 칩에서 사용한다.
class ElapsedTimerText extends StatefulWidget {
  const ElapsedTimerText({super.key, this.style, this.showHours = true});

  final TextStyle? style;

  /// true면 `00:00:07`, false면 `00:07` 형식.
  final bool showHours;

  @override
  State<ElapsedTimerText> createState() => _ElapsedTimerTextState();
}

class _ElapsedTimerTextState extends State<ElapsedTimerText> {
  final Stopwatch _stopwatch = Stopwatch()..start();
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  String _format(Duration d) {
    String two(int n) => n.toString().padLeft(2, '0');
    final m = two(d.inMinutes.remainder(60));
    final s = two(d.inSeconds.remainder(60));
    return widget.showHours ? '${two(d.inHours)}:$m:$s' : '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Text(_format(_stopwatch.elapsed), style: widget.style);
  }
}
