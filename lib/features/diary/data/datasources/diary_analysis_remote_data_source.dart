import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';

import '../../../../core/error/app_exception.dart';
import '../../../../core/network/api_client.dart';
import '../../../baseline/data/models/baseline_profile.dart';
import '../models/fusion_result.dart';
import 'diary_analysis_data_source.dart';

/// 실제 AI 서버(`POST /diary/step2/analyze`) 호출. baseline은 서버가 아직
/// Firestore에서 직접 읽지 않아서(step2.py TODO) 클라이언트가 함께 전달한다.
class DiaryAnalysisRemoteDataSource implements DiaryAnalysisDataSource {
  DiaryAnalysisRemoteDataSource(this._apiClient, {FirebaseAuth? auth})
    : _auth = auth ?? FirebaseAuth.instance;

  final ApiClient _apiClient;
  final FirebaseAuth _auth;

  @override
  Future<FusionResult> analyzeStep2({
    required String text,
    required String voiceFilePath,
    required String faceImagePath,
    required BaselineProfile baseline,
  }) async {
    final json = await _apiClient.postMultipart(
      '/diary/step2/analyze',
      fields: {
        'text': text,
        'baseline_voice': jsonEncode(baseline.voice),
        'baseline_face': jsonEncode(baseline.face),
        'user_id': ?_auth.currentUser?.uid,
      },
      filePaths: {'voice_file': voiceFilePath, 'face_image': faceImagePath},
    );
    try {
      return FusionResult.fromJson(json);
    } catch (e) {
      throw ServerException('감정 분석 응답을 처리하지 못했어요.', e);
    }
  }
}
