"""컷 그림을 잠깐 공개 주소(URL)로 만든다 — evolink 영상 모델은 그림을 URL로만 받는다.

Firebase Storage(앱이 영상을 보관하는 버킷)의 `videomake-tmp/`에 올리고 서명된 주소(만료 있음)를
돌려준다. 버킷 규칙(storage.rules)은 앱 사용자용이고, 서버는 서비스 계정으로 올린다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from ..errors import ConfigError, ProviderError

log = logging.getLogger(__name__)

URL_LIFETIME = timedelta(hours=3)  # 영상 렌더(수 분)와 재시도에 충분하다


class FirebaseImageHost:
    def __init__(self, bucket: str, credentials_path: str, prefix: str = "videomake-tmp") -> None:
        if not credentials_path or not Path(credentials_path).exists():
            raise ConfigError(
                "evolink 영상 모델은 그림을 URL로 받는다. 그림을 올릴 서비스 계정 키가 필요하다 "
                f"(GOOGLE_APPLICATION_CREDENTIALS={credentials_path!r})."
            )
        self._bucket_name = bucket
        self._credentials_path = credentials_path
        self._prefix = prefix
        self._bucket = None

    def _get_bucket(self):
        if self._bucket is None:
            from google.cloud import storage

            client = storage.Client.from_service_account_json(self._credentials_path)
            self._bucket = client.bucket(self._bucket_name)
        return self._bucket

    async def url_for(self, path: Path, key: str) -> str:
        """path를 `{prefix}/{key}`로 올리고 서명된 GET 주소를 돌려준다."""

        def upload() -> str:
            blob = self._get_bucket().blob(f"{self._prefix}/{key}")
            blob.upload_from_filename(str(path))
            return blob.generate_signed_url(version="v4", expiration=URL_LIFETIME, method="GET")

        try:
            return await asyncio.to_thread(upload)
        except Exception as exc:
            raise ProviderError(f"그림 업로드 실패({path.name}): {exc}") from exc
