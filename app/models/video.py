from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class VideoJobRequest(BaseModel):
    """Step3 영상 생성 요청. 감정 필드는 `/diary/step2/analyze` 응답을 그대로 넘긴다."""

    text: str = Field(..., min_length=1, max_length=5000, description="일기 원문(Step2 확인본)")
    emotion_keywords: list[str] = Field(default_factory=list, description="Step2 emotion_keywords")
    emotion_scores: dict[str, float] = Field(
        default_factory=dict, description="Step2 emotion_scores (0~100)"
    )
    emotion_intensity: int | None = Field(None, ge=0, le=100, description="Step2 emotion_intensity")
    protagonist_name: str | None = Field(
        None, max_length=10, description="영상 속 인물 이름. 없으면 LLM이 짓는다"
    )
    diary_handoff: dict[str, Any] | None = Field(
        None,
        description=(
            "일기 기록 뒤 만든 영상 전달 JSON(oddo.diary_emotion.v1, /diary/handoff의 video) — "
            "장면·전환점·문장별 감정·정제 일기·대화 칸. 앱이 있으면 그대로 싣는다. "
            "스토리보드는 정제 일기를 일기 글로 쓰고 장면·전환점·대화 칸·표정 변화를 "
            "컷 구성 근거로 쓴다. 없거나 형식이 다르면 text·감정만으로 만든다"
        ),
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


VideoJobState = Literal["running", "done", "failed"]
VideoStage = Literal["storyboard", "images", "videos", "narration", "compose", "done"]


class VideoJobStatus(BaseModel):
    job_id: str
    status: VideoJobState
    stage: VideoStage = Field(..., description="지금 진행 중인(또는 마지막) 단계")
    progress: float = Field(..., ge=0, le=1, description="0~1 — 앱 로딩 화면 진행률")
    error: str | None = Field(None, description="status=failed일 때 사용자에게 보여줄 메시지")
    video_url: str | None = Field(
        None, description="status=done일 때 mp4 경로(서버 기준 상대 경로)"
    )
    thumbnail_url: str | None = Field(
        None,
        description=(
            "status=done이고 썸네일이 있을 때 대표 장면 가로(16:9) jpg 경로(서버 기준 상대 경로). "
            "썸네일 생성에 실패하면 null — 영상은 그대로 볼 수 있다"
        ),
    )
