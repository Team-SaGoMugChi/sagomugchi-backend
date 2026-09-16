"""Real model smoke check: python -m scripts.smoke_kote (not an accuracy benchmark)."""

import json
import time

from fastapi.testclient import TestClient

from app.main import app
from app.services.text_emotion import EMOTION_LABELS


def main():
    with TestClient(app) as client:
        for text in (
            '친구들과 즐겁게 놀아서 정말 행복한 하루였어.',
            '내일 발표에서 실수할까 봐 너무 불안하고 걱정돼.',
            '친구가 내 말을 무시해서 서운하고 실망했어.',
            '오늘은 월요일이고 책상 위에 연필이 세 자루 있다.',
            '오늘 있었던 일을 천천히 정리하고 있다. ' * 80 + '친구에게 배신당해서 너무 슬프다.',
        ):
            start = time.perf_counter()
            response = client.post('/analyze/text', json={'text': text})
            response.raise_for_status()
            body = response.json()
            assert set(body['scores']) == set(EMOTION_LABELS)
            assert all(0 <= value <= 1 for value in body['scores'].values())
            assert body['dominant_emotion'] in EMOTION_LABELS or body['dominant_emotion'] is None
            print(json.dumps({'chars': len(text), 'seconds': round(time.perf_counter() - start, 3), **body}, ensure_ascii=False))

        # Synthetic media exercise the actual Step2 route without a camera or DB.
        import io
        import cv2
        import numpy as np
        import soundfile as sf

        audio = io.BytesIO()
        sf.write(audio, 0.1 * np.sin(2 * np.pi * 220 * np.arange(22050) / 22050), 22050, format='WAV')
        ok, png = cv2.imencode('.png', np.zeros((240, 320, 3), dtype=np.uint8))
        assert ok
        response = client.post('/diary/step2/analyze', data={'text': '오늘 친구를 만나서 행복했어.'},
                               files={'voice_file': ('voice.wav', audio.getvalue(), 'audio/wav'),
                                      'face_image': ('face.png', png.tobytes(), 'image/png')})
        response.raise_for_status()
        assert set(response.json()['text_emotion_scores']) == set(EMOTION_LABELS)
        print(json.dumps({'step2_status': response.status_code, 'keywords': response.json()['emotion_keywords']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
