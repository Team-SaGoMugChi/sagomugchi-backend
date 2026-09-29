"""도메인 예외. FastAPI 이식 시 HTTP 상태로 매핑하기 쉽도록 계층을 얕게 유지한다."""


class VideomakeError(Exception):
    """모든 도메인 예외의 루트."""


class ConfigError(VideomakeError):
    """설정/자격증명 문제."""


class GuardrailViolation(VideomakeError):
    """연출 원칙 위반. 생성물을 그대로 통과시키면 안 된다."""


class ApprovalRequired(VideomakeError):
    """승인 게이트를 통과하지 않은 채 영상 렌더를 시도했다."""


class BudgetExceeded(VideomakeError):
    """예상 비용이 상한을 넘었고 명시적 확인이 없다."""


class ProviderError(VideomakeError):
    """외부 생성 모델 호출 실패."""


class RenderTimeout(ProviderError):
    """long-running operation이 제한 시간 안에 끝나지 않았다."""
