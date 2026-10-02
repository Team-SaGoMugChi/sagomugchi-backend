import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.baseline import BaselineProfile
from app.services.baseline_repository import save_baseline_profile
from app.services.baseline_service import BaselineMeasurementError, build_baseline_profile

router = APIRouter(tags=["baseline"])
logger = logging.getLogger(__name__)


@router.post("/baseline", response_model=BaselineProfile)
async def create_baseline(
    user_id: str = Form(...),
    voice_file: UploadFile = File(...),
    face_image: UploadFile | None = File(None),
    face_images: list[UploadFile] | None = File(None),
    face_timeline: str | None = Form(None),
) -> BaselineProfile:
    voice_bytes = await voice_file.read()
    uploads = list(face_images or [])
    if face_image is not None:
        uploads.append(face_image)
    face_bytes = [content for upload in uploads if (content := await upload.read())]
    try:
        kwargs = {"face_timeline": face_timeline} if face_timeline is not None else {}
        profile = build_baseline_profile(user_id=user_id, voice_bytes=voice_bytes, face_image_bytes=face_bytes, **kwargs)
    except BaselineMeasurementError as exc:
        logger.warning("Baseline measurement rejected: %s", exc.code)
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    save_baseline_profile(profile)
    return profile
