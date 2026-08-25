from fastapi import APIRouter, UploadFile

from app.models.face import FaceAnalysisResult
from app.services.face_analysis import analyze_face

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/face", response_model=FaceAnalysisResult)
async def analyze_face_endpoint(file: UploadFile) -> FaceAnalysisResult:
    image_bytes = await file.read()
    return analyze_face(image_bytes)
