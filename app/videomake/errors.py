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


class VideoBlocked(ProviderError):
    """영상 AI가 안전 필터로 컷을 거절했다. 과금되지 않으며 그림을 바꾸면 통과할 수 있다."""

    def __init__(self, message: str, *, cuts: set[int]) -> None:
        super().__init__(message)
        self.cuts = cuts


class RenderTimeout(ProviderError):
    """long-running operation이 제한 시간 안에 끝나지 않았다."""
