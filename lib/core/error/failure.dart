/// Domain-level failures surfaced by repositories.
///
/// Repositories translate low-level exceptions (network, parsing, cache) into
/// one of these so the UI can handle them uniformly. Kept as a sealed class so
/// `switch` over failures is exhaustive.
sealed class Failure {
  const Failure(this.message);
  final String message;

  @override
  String toString() => '$runtimeType($message)';
}

class NetworkFailure extends Failure {
  const NetworkFailure([super.message = '네트워크 연결이 불안정해요.']);
}

class ServerFailure extends Failure {
  const ServerFailure([super.message = '일시적인 오류가 발생했어요.']);
}

class CacheFailure extends Failure {
  const CacheFailure([super.message = '저장된 데이터를 불러오지 못했어요.']);
}

class AuthFailure extends Failure {
  const AuthFailure([super.message = '인증에 실패했어요.']);
}

class UnknownFailure extends Failure {
  const UnknownFailure([super.message = '알 수 없는 오류가 발생했어요.']);
}
