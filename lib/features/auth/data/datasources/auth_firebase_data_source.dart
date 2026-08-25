import 'dart:convert';
import 'dart:math';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:crypto/crypto.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/services.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart' as kakao;

import '../../../../core/error/app_exception.dart';
import '../models/app_user.dart';
import '../models/social_login_result.dart';
import 'auth_data_source.dart';

/// Real auth: FirebaseAuth for credentials + the `users/{uid}` Firestore
/// document for the profile (FIRESTORE_SCHEMA.md).
///
/// Every FirebaseAuthException is mapped to an [AuthException] with a
/// user-facing Korean message, so screens can show it as-is.
class AuthFirebaseDataSource implements AuthDataSource {
  AuthFirebaseDataSource({
    FirebaseAuth? auth,
    FirebaseFirestore? firestore,
    GoogleSignIn? googleSignIn,
  })  : _auth = auth ?? FirebaseAuth.instance,
        _firestore = firestore ?? FirebaseFirestore.instance,
        _googleSignIn = googleSignIn ?? GoogleSignIn();

  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;
  final GoogleSignIn _googleSignIn;

  DocumentReference<Map<String, dynamic>> _userDoc(String uid) =>
      _firestore.collection('users').doc(uid);

  @override
  Future<AppUser?> currentUser() async {
    final user = _auth.currentUser;
    if (user == null) return null;
    return _guard(() => _loadOrCreateProfile(user));
  }

  @override
  Future<AppUser> login({
    required String email,
    required String password,
  }) {
    return _guard(() async {
      final credential = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      return _loadOrCreateProfile(credential.user!);
    });
  }

  @override
  Future<AppUser> signUp({
    required String email,
    required String password,
    required String nickname,
  }) {
    return _guard(() async {
      final credential = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      final user = AppUser(
        id: credential.user!.uid,
        email: email,
        nickname: nickname,
        onboardingDone: false,
        createdAt: DateTime.now(),
      );
      await _userDoc(user.id).set(user.toJson());
      return user;
    });
  }

  @override
  Future<SocialLoginResult> loginWithGoogle() {
    return _guard(() async {
      final googleUser = await _googleSignIn.signIn();
      if (googleUser == null) {
        return const SocialLoginResult(SocialLoginStatus.cancelled);
      }
      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );
      final userCredential = await _auth.signInWithCredential(credential);

      final snapshot = await _userDoc(userCredential.user!.uid).get();
      final data = snapshot.data();
      if (data == null) {
        // First-time social user — profile comes from the extra-info screen.
        return const SocialLoginResult(SocialLoginStatus.needsProfile);
      }
      return SocialLoginResult(SocialLoginStatus.success, AppUser.fromJson(data));
    });
  }

  @override
  Future<SocialLoginResult> loginWithKakao() {
    return _guard(() async {
      // Firebase verifies the id_token's nonce claim against SHA256(rawNonce),
      // so Kakao gets the hash and Firebase gets the raw value.
      final rawNonce = _randomNonce();
      final hashedNonce = sha256.convert(utf8.encode(rawNonce)).toString();

      kakao.OAuthToken token;
      try {
        if (await kakao.isKakaoTalkInstalled()) {
          try {
            token = await kakao.UserApi.instance
                .loginWithKakaoTalk(nonce: hashedNonce);
          } on PlatformException catch (e) {
            if (e.code == 'CANCELED') {
              return const SocialLoginResult(SocialLoginStatus.cancelled);
            }
            // 카카오톡은 있지만 실패(미로그인 등) → 계정(웹) 로그인으로 폴백.
            token = await kakao.UserApi.instance
                .loginWithKakaoAccount(nonce: hashedNonce);
          }
        } else {
          token = await kakao.UserApi.instance
              .loginWithKakaoAccount(nonce: hashedNonce);
        }
      } on kakao.KakaoClientException catch (e) {
        if (e.reason == kakao.ClientErrorCause.cancelled) {
          return const SocialLoginResult(SocialLoginStatus.cancelled);
        }
        throw AuthException('카카오 로그인에 실패했어요. 잠시 후 다시 시도해주세요.',
            cause: e);
      } on kakao.KakaoAuthException catch (e) {
        if (e.error == kakao.AuthErrorCause.accessDenied) {
          return const SocialLoginResult(SocialLoginStatus.cancelled);
        }
        throw AuthException('카카오 로그인에 실패했어요. 잠시 후 다시 시도해주세요.',
            cause: e);
      }

      final idToken = token.idToken;
      if (idToken == null) {
        throw const AuthException(
            '카카오 로그인 설정(OpenID Connect)이 아직 준비되지 않았어요.');
      }
      final credential = OAuthProvider('oidc.kakao').credential(
        idToken: idToken,
        rawNonce: rawNonce,
      );
      final userCredential = await _auth.signInWithCredential(credential);

      final snapshot = await _userDoc(userCredential.user!.uid).get();
      final data = snapshot.data();
      if (data == null) {
        return const SocialLoginResult(SocialLoginStatus.needsProfile);
      }
      return SocialLoginResult(SocialLoginStatus.success, AppUser.fromJson(data));
    });
  }

  static String _randomNonce([int length = 32]) {
    const chars =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    final random = Random.secure();
    return List.generate(length, (_) => chars[random.nextInt(chars.length)])
        .join();
  }

  @override
  Future<AppUser> completeSocialProfile({required String nickname}) {
    return _guard(() async {
      final firebaseUser = _auth.currentUser;
      if (firebaseUser == null) {
        throw const AuthException('로그인 정보가 만료됐어요. 다시 로그인해주세요.');
      }
      final user = AppUser(
        id: firebaseUser.uid,
        email: firebaseUser.email ?? '',
        nickname: nickname,
        onboardingDone: false,
        createdAt: DateTime.now(),
      );
      await _userDoc(user.id).set(user.toJson());
      return user;
    });
  }

  @override
  Future<void> sendPasswordReset({required String email}) {
    return _guard(() => _auth.sendPasswordResetEmail(email: email));
  }

  @override
  Future<void> updateOnboardingDone({required bool done}) {
    return _guard(() async {
      final uid = _auth.currentUser?.uid;
      if (uid == null) return;
      await _userDoc(uid).update({'onboardingDone': done});
    });
  }

  @override
  Future<void> updateNickname({required String nickname}) {
    return _guard(() async {
      final uid = _auth.currentUser?.uid;
      if (uid == null) {
        throw const AuthException('로그인이 필요해요. 다시 로그인해주세요.');
      }
      await _userDoc(uid).update({'nickname': nickname});
    });
  }

  @override
  Future<bool> hasPasswordLogin() async {
    final user = _auth.currentUser;
    if (user == null) return false;
    return user.providerData.any((p) => p.providerId == 'password');
  }

  @override
  Future<void> logout() {
    return _guard(() async {
      // Also drop the social sessions so account pickers show next time.
      await _googleSignIn.signOut();
      try {
        await kakao.UserApi.instance.logout();
      } catch (_) {
        // No Kakao session (email/Google user) — nothing to do.
      }
      await _auth.signOut();
    });
  }

  @override
  Future<void> deleteAccount() {
    return _guard(() async {
      final user = _auth.currentUser;
      if (user == null) return;
      await _userDoc(user.uid).delete();
      await user.delete();
    });
  }

  /// Reads the `users/{uid}` profile; creates it from the auth account when
  /// missing (e.g. doc lost or created before the schema landed).
  Future<AppUser> _loadOrCreateProfile(User firebaseUser) async {
    final snapshot = await _userDoc(firebaseUser.uid).get();
    final data = snapshot.data();
    if (data != null) return AppUser.fromJson(data);

    final fallback = AppUser(
      id: firebaseUser.uid,
      email: firebaseUser.email ?? '',
      nickname: firebaseUser.displayName ?? '오또 사용자',
      onboardingDone: false,
      createdAt: DateTime.now(),
    );
    await _userDoc(fallback.id).set(fallback.toJson());
    return fallback;
  }

  /// Maps Firebase/plugin exceptions to app-level ones with user-facing
  /// messages.
  Future<T> _guard<T>(Future<T> Function() run) async {
    try {
      return await run();
    } on FirebaseAuthException catch (e) {
      throw AuthException(_messageFor(e.code), code: e.code, cause: e);
    } on FirebaseException catch (e) {
      if (e.code == 'unavailable') {
        throw NetworkException('네트워크 연결이 불안정해요.', e);
      }
      throw AuthException('일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.',
          code: e.code, cause: e);
    } on PlatformException catch (e) {
      // google_sign_in surfaces device/config errors this way.
      throw AuthException('구글 로그인에 실패했어요. 잠시 후 다시 시도해주세요.',
          code: e.code, cause: e);
    }
  }

  static String _messageFor(String code) => switch (code) {
        'invalid-email' => '이메일 형식이 올바르지 않아요.',
        'user-not-found' ||
        'wrong-password' ||
        'invalid-credential' =>
          '이메일 또는 비밀번호가 올바르지 않아요.',
        'email-already-in-use' => '이미 가입된 이메일이에요.',
        'weak-password' => '비밀번호는 6자 이상으로 만들어주세요.',
        'user-disabled' => '사용이 중지된 계정이에요. 고객센터로 문의해주세요.',
        'too-many-requests' => '시도가 너무 많았어요. 잠시 후 다시 시도해주세요.',
        'network-request-failed' => '네트워크 연결이 불안정해요.',
        'requires-recent-login' => '보안을 위해 다시 로그인한 뒤 시도해주세요.',
        _ => '일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.',
      };
}
