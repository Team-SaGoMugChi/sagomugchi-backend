from fastapi import APIRouter

from app.api.routes import baseline, face, health, step2, voice

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(voice.router)
api_router.include_router(face.router)
api_router.include_router(baseline.router)
api_router.include_router(step2.router)
