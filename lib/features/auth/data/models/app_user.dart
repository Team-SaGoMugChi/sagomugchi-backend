/// Domain model for an authenticated user.
///
/// Stored at `users/{uid}` — see FIRESTORE_SCHEMA.md.
class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.nickname,
    this.onboardingDone = false,
    this.createdAt,
  });

  final String id;
  final String email;
  final String nickname;

  /// Whether the user has finished baseline + psych test + persona onboarding.
  final bool onboardingDone;

  /// Signup time (null for pre-schema dummy data).
  final DateTime? createdAt;

  AppUser copyWith({
    String? id,
    String? email,
    String? nickname,
    bool? onboardingDone,
    DateTime? createdAt,
  }) {
    return AppUser(
      id: id ?? this.id,
      email: email ?? this.email,
      nickname: nickname ?? this.nickname,
      onboardingDone: onboardingDone ?? this.onboardingDone,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as String,
        email: json['email'] as String,
        nickname: json['nickname'] as String,
        onboardingDone: json['onboardingDone'] as bool? ?? false,
        createdAt: json['createdAt'] != null
            ? DateTime.parse(json['createdAt'] as String)
            : null,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'nickname': nickname,
        'onboardingDone': onboardingDone,
        if (createdAt != null) 'createdAt': createdAt!.toIso8601String(),
      };
}
