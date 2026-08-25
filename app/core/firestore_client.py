"""Firebase Admin SDK 초기화 + Firestore 클라이언트.

firestore.rules는 request.auth.uid == uid인 클라이언트 쓰기만 허용하므로, 서버가
사용자 대신 쓰려면 Admin SDK(서비스 계정)로 규칙을 우회해야 한다.
로컬 개발: .env의 GOOGLE_APPLICATION_CREDENTIALS에 서비스 계정 키(JSON) 경로 지정.
"""

from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import get_settings


@lru_cache
def get_firestore_client():
    if not firebase_admin._apps:
        settings = get_settings()
        cred = (
            credentials.Certificate(settings.google_application_credentials)
            if settings.google_application_credentials
            else credentials.ApplicationDefault()
        )
        firebase_admin.initialize_app(cred)

    return firestore.client()
