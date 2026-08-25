/// Common durations used for animations and simulated async latency.
abstract final class AppDurations {
  AppDurations._();

  /// Simulated network/processing latency for dummy data sources.
  static const Duration dummyLatency = Duration(milliseconds: 600);

  /// Simulated longer task (e.g. baseline analysis, video creation).
  static const Duration dummyLongTask = Duration(seconds: 2);

  static const Duration fast = Duration(milliseconds: 150);
  static const Duration medium = Duration(milliseconds: 250);
  static const Duration slow = Duration(milliseconds: 400);
}
