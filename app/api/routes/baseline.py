from fastapi import APIRouter, File, Form, UploadFile

from app.models.baseline import BaselineProfile
from app.services.baseline_repository import save_baseline_profile
from app.services.baseline_service import build_baseline_profile

router = APIRouter(tags=["baseline"])


@router.post("/baseline", response_model=BaselineProfile)
async def create_baseline(
    user_id: str = Form(...),
    voice_file: UploadFile = File(...),
    face_image: UploadFile = File(...),
) -> BaselineProfile:
    voice_bytes = await voice_file.read()
    face_bytes = await face_image.read()
    profile = build_baseline_profile(user_id=user_id, voice_bytes=voice_bytes, face_image_bytes=face_bytes)
    save_baseline_profile(profile)
    return profile
