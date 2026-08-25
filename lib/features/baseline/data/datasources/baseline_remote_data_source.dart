import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/error/app_exception.dart';
import '../../../../core/network/api_client.dart';
import '../models/baseline_profile.dart';
import 'baseline_data_source.dart';

/// 실제 AI 서버(`POST /baseline`) 호출. 응답 필드는 FastAPI(Pydantic) 쪽 스네이크
/// 케이스(`measured_at`)라 Firestore 컨벤션(camelCase)과 다르다 — 여기서 직접 조립해서
/// [BaselineProfile.fromJson](Firestore 읽기용)과 헷갈리지 않게 분리해둔다.
///
/// 저장은 서버가 Admin SDK로 `users/{uid}/meta/baseline`에 직접 쓰지만([upload]
/// 호출 시 서버 쪽 `baseline_repository.py`), 읽기는 앱이 다른 사용자 데이터와
/// 같은 방식으로 클라이언트에서 바로 Firestore를 읽는다(diary와 동일 패턴) —
/// 단순 문서 조회에 서버 왕복이 필요 없다.
class BaselineRemoteDataSource implements BaselineDataSource {
  BaselineRemoteDataSource(
    this._apiClient, {
    FirebaseAuth? auth,
    FirebaseFirestore? firestore,
  }) : _auth = auth ?? FirebaseAuth.instance,
       _firestore = firestore ?? FirebaseFirestore.instance;

  final ApiClient _apiClient;
  final FirebaseAuth _auth;
  final FirebaseFirestore _firestore;

  String get _uid {
    final uid = _auth.currentUser?.uid;
    if (uid == null) {
      throw const AuthException('로그인이 필요해요. 다시 로그인해주세요.');
    }
    return uid;
  }

  @override
  Future<BaselineProfile> upload({
    required String voiceFilePath,
    required String faceImagePath,
  }) async {
    final json = await _apiClient.postMultipart(
      '/baseline',
      fields: {'user_id': _uid},
      filePaths: {'voice_file': voiceFilePath, 'face_image': faceImagePath},
    );

    return BaselineProfile(
      voice: _toDoubleMap(json['voice']),
      face: _toDoubleMap(json['face']),
      measuredAt: DateTime.parse(json['measured_at'] as String),
    );
  }

  @override
  Future<BaselineProfile?> fetchSaved() async {
    try {
      final doc = await _firestore
          .collection('users')
          .doc(_uid)
          .collection('meta')
          .doc('baseline')
          .get();
      final data = doc.data();
      return data != null ? BaselineProfile.fromJson(data) : null;
    } on FirebaseException catch (e) {
      if (e.code == 'unavailable') {
        throw NetworkException('네트워크 연결이 불안정해요.', e);
      }
      throw ServerException('baseline 정보를 불러오지 못했어요.', e);
    }
  }

  Map<String, double> _toDoubleMap(Object? raw) {
    final map = raw as Map<String, dynamic>? ?? {};
    return map.map((k, v) => MapEntry(k, (v as num).toDouble()));
  }
}
