from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models.video import VideoJobRequest, VideoJobStatus
from app.services.video_job import VideoJobManager, get_video_jobs

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/jobs", response_model=VideoJobStatus, status_code=202)
async def create_video_job(
    payload: VideoJobRequest,
    background: BackgroundTasks,
    jobs: VideoJobManager = Depends(get_video_jobs),
) -> VideoJobStatus:
    """Step3 영상 생성을 시작한다. 응답의 job_id로 상태를 폴링한다."""
    job_id = jobs.create()
    background.add_task(jobs.run, job_id, payload)
    return jobs.status(job_id)


@router.get("/jobs/{job_id}", response_model=VideoJobStatus)
def get_video_job(
    job_id: str, jobs: VideoJobManager = Depends(get_video_jobs)
) -> VideoJobStatus:
    status = jobs.status(job_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "영상 작업을 찾지 못했어요."},
        )
    return status


@router.get("/jobs/{job_id}/file")
def get_video_file(
    job_id: str, jobs: VideoJobManager = Depends(get_video_jobs)
) -> FileResponse:
    path = jobs.final_path(job_id)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "video_not_ready", "message": "영상이 아직 준비되지 않았어요."},
        )
    return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")
