import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config_provider.dart';
import '../error/app_exception.dart';

/// HTTP client used by remote data sources (the FastAPI AI server).
///
/// Implementations throw [AppException] subtypes only — repositories catch
/// those and map them to [Failure]s, so the UI never sees raw dio errors.
abstract interface class ApiClient {
  Future<Map<String, dynamic>> get(String path, {Map<String, dynamic>? query});

  Future<Map<String, dynamic>> post(String path, {Object? body});

  /// multipart/form-data POST — 음성/얼굴 파일 업로드용(baseline, 일기 Step1 등).
  /// [filePaths]의 값은 로컬 파일 경로이고, 필드명은 FastAPI 쪽 `File(...)` 파라미터
  /// 이름과 맞춰야 한다.
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    Map<String, String> fields,
    Map<String, String> filePaths,
  });
}

/// Returns the bearer token to attach to requests, or null for none.
/// Wired to the Firebase ID token once auth lands (Phase 1).
typedef AuthTokenProvider = Future<String?> Function();

/// dio-backed [ApiClient]. Base URL comes from [AppConfig.apiBaseUrl];
/// an optional [AuthTokenProvider] attaches `Authorization: Bearer <token>`.
class DioApiClient implements ApiClient {
  DioApiClient({
    required String baseUrl,
    AuthTokenProvider? tokenProvider,
    Dio? dio,
  }) : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl,
                connectTimeout: const Duration(seconds: 10),
                receiveTimeout: const Duration(seconds: 60),
                contentType: Headers.jsonContentType,
              ),
            ) {
    if (tokenProvider != null) {
      _dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) async {
            final token = await tokenProvider();
            if (token != null) {
              options.headers['Authorization'] = 'Bearer $token';
            }
            handler.next(options);
          },
        ),
      );
    }
  }

  final Dio _dio;

  @override
  Future<Map<String, dynamic>> get(
    String path, {
    Map<String, dynamic>? query,
  }) =>
      _request(() => _dio.get<Map<String, dynamic>>(
            path,
            queryParameters: query,
          ));

  @override
  Future<Map<String, dynamic>> post(String path, {Object? body}) =>
      _request(() => _dio.post<Map<String, dynamic>>(path, data: body));

  @override
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    Map<String, String> fields = const {},
    Map<String, String> filePaths = const {},
  }) =>
      _request(() async {
        final formData = FormData.fromMap({
          ...fields,
          for (final entry in filePaths.entries)
            entry.key: await MultipartFile.fromFile(entry.value),
        });
        return _dio.post<Map<String, dynamic>>(path, data: formData);
      });

  /// Runs [send] and normalizes every failure mode into an [AppException].
  Future<Map<String, dynamic>> _request(
    Future<Response<Map<String, dynamic>>> Function() send,
  ) async {
    try {
      final response = await send();
      return response.data ?? const {};
    } on DioException catch (e) {
      throw switch (e.type) {
        DioExceptionType.connectionTimeout ||
        DioExceptionType.sendTimeout ||
        DioExceptionType.receiveTimeout ||
        DioExceptionType.connectionError =>
          NetworkException('Network error: ${e.message}', e),
        DioExceptionType.badResponse => ServerException(
            'Server responded ${e.response?.statusCode}', e),
        _ => ServerException('Request failed: ${e.message}', e),
      };
    }
  }
}

/// App-wide [ApiClient], pointed at [AppConfig.apiBaseUrl].
///
/// Remote data sources read this instead of constructing their own client, so
/// auth headers/logging stay in one place. The token provider is attached in
/// Phase 1 (auth) by overriding or extending this provider.
final apiClientProvider = Provider<ApiClient>((ref) {
  final config = ref.watch(appConfigProvider);
  return DioApiClient(baseUrl: config.apiBaseUrl);
});
