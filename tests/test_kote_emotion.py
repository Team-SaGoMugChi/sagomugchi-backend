from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.kote_emotion import (
    EXPECTED_LABELS, MAX_TEXT_LENGTH, MODEL_ID, MAPPING_VERSION,
    KoteTextEmotionClassifier, TextEmotionUnavailable, project_six,
)
from app.services.text_emotion import EMOTION_LABELS, get_text_emotion_classifier


def native(**values):
    return dict.fromkeys(EXPECTED_LABELS, 0.01) | values


@pytest.mark.parametrize(('label', 'expected'), [
    ('행복', '기쁨'), ('슬픔', '슬픔'), ('화남/분노', '분노'),
    ('불안/걱정', '불안'), ('안타까움/실망', '상처'), ('당황/난처', '당황'),
])
def test_six_class_projection(label, expected):
    result = project_six(native(**{label: 0.8}))
    assert set(result.scores) == set(EMOTION_LABELS)
    assert result.dominant_emotion == expected
    assert sum(result.scores.values()) == pytest.approx(1)
    assert result.confidence == 0.8  # Not normalized certainty of 1.0.


def test_multiple_emotions_survive_and_group_size_does_not_add_mass():
    result = project_six(native(**{'행복': 0.8, '기쁨': 0.8, '슬픔': 0.8}))
    assert result.scores['기쁨'] == result.scores['슬픔'] == 0.5


@pytest.mark.parametrize('values', [{}, {'없음': 0.9, '기쁨': 0.8}, {'깨달음': 0.9}])
def test_unknown_has_six_zero_scores_not_forced_joy(values):
    result = project_six(native(**values))
    assert result.dominant_emotion is None
    assert result.confidence == 0
    assert result.scores == dict.fromkeys(EMOTION_LABELS, 0.0)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -0.1, 1.1])
def test_rejects_corrupt_model_output(value):
    with pytest.raises(TextEmotionUnavailable):
        project_six(native(**{'기쁨': value}))


def test_rejects_missing_labels():
    with pytest.raises(TextEmotionUnavailable):
        project_six({'기쁨': 0.9})


@pytest.mark.parametrize('text', ['', ' \n ', '가' * (MAX_TEXT_LENGTH + 1)], ids=['empty', 'blank', 'oversized'])
def test_invalid_text_never_loads_weights(text, monkeypatch):
    classifier = KoteTextEmotionClassifier()
    monkeypatch.setattr(classifier, '_load', lambda: pytest.fail('must not load'))
    with pytest.raises(ValueError):
        classifier.classify(text)


def test_factory_defaults_to_cached_kote():
    get_text_emotion_classifier.cache_clear()
    try:
        classifier = get_text_emotion_classifier()
        assert isinstance(classifier, KoteTextEmotionClassifier)
        assert get_text_emotion_classifier() is classifier
    finally:
        get_text_emotion_classifier.cache_clear()


def test_chunked_inference_uses_sigmoid_and_includes_tail():
    torch = pytest.importorskip('torch')
    labels = sorted(EXPECTED_LABELS)
    calls = []

    class Inputs(dict):
        def to(self, device):
            return self

    class Tokenizer:
        def __call__(self, text, **kwargs):
            assert kwargs['truncation'] is False
            return {'input_ids': [1, 2, 3, 4, 5, 6]}

        def num_special_tokens_to_add(self, pair):
            return 2

        def prepare_for_model(self, chunk, **kwargs):
            assert kwargs['prepend_batch_axis'] is True
            calls.append(chunk)
            return Inputs(input_ids=torch.tensor([chunk]))

    class Model:
        config = SimpleNamespace(max_position_embeddings=6)

        def __call__(self, **inputs):
            logits = torch.full((1, 44), -10.0)
            label = '기쁨' if inputs['input_ids'][0, 0] == 1 else '슬픔'
            logits[0, labels.index(label)] = 2.0
            return SimpleNamespace(logits=logits)

    classifier = KoteTextEmotionClassifier(threshold=0.2)
    classifier._runtime = torch, Tokenizer(), Model(), labels
    result = classifier.classify('long diary')
    assert calls == [[1, 2, 3, 4], [5, 6]]
    assert result.scores['기쁨'] == pytest.approx(2 / 3, abs=0.001)
    assert result.scores['슬픔'] == pytest.approx(1 / 3, abs=0.001)
    assert result.confidence == pytest.approx(0.5872, abs=0.001)


def test_real_tokenizer_creates_batched_model_inputs(tmp_path):
    torch = pytest.importorskip('torch')
    transformers = pytest.importorskip('transformers')
    vocab = tmp_path / 'vocab.txt'
    vocab.write_text('[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nhappy\n', encoding='utf-8')
    tokenizer = transformers.BertTokenizerFast(vocab_file=str(vocab))
    labels = sorted(EXPECTED_LABELS)

    class Model:
        config = SimpleNamespace(max_position_embeddings=512)

        def __call__(self, **inputs):
            assert inputs['input_ids'].ndim == 2
            assert inputs['input_ids'].shape[0] == 1
            assert inputs['attention_mask'].shape == inputs['input_ids'].shape
            logits = torch.full((1, 44), -10.0)
            logits[0, labels.index('기쁨')] = 2.0
            return SimpleNamespace(logits=logits)

    classifier = KoteTextEmotionClassifier()
    classifier._runtime = torch, tokenizer, Model(), labels
    assert classifier.classify('happy').dominant_emotion == '기쁨'


def test_model_value_error_is_unavailability_not_bad_user_input():
    torch = pytest.importorskip('torch')
    def fail(*args, **kwargs):
        raise ValueError('tensor shape mismatch')
    classifier = KoteTextEmotionClassifier()
    classifier._runtime = torch, fail, None, sorted(EXPECTED_LABELS)
    with pytest.raises(TextEmotionUnavailable):
        classifier.classify('정상 입력')


def test_text_endpoint_keeps_six_label_contract(monkeypatch):
    result = project_six(native(**{'불안/걱정': 0.9}))
    monkeypatch.setattr('app.api.routes.text_emotion.get_text_emotion_classifier',
                        lambda: SimpleNamespace(classify=lambda text: result))
    response = TestClient(app).post('/analyze/text', json={'text': '내일 시험이 걱정돼'})
    assert response.status_code == 200
    body = response.json()
    assert body['dominant_emotion'] == '불안'
    assert set(body['scores']) == set(EMOTION_LABELS)
    assert body['model_id'] == MODEL_ID
    assert body['mapping_version'] == MAPPING_VERSION


def test_model_failure_is_503_not_keyword_result(monkeypatch):
    def fail(text):
        raise TextEmotionUnavailable('private cache path')
    monkeypatch.setattr('app.api.routes.text_emotion.get_text_emotion_classifier',
                        lambda: SimpleNamespace(classify=fail))
    response = TestClient(app).post('/analyze/text', json={'text': '행복하다'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'text_emotion_unavailable'
    assert 'private cache path' not in response.text


@pytest.mark.parametrize('text', ['', ' \n ', '가' * (MAX_TEXT_LENGTH + 1)], ids=['empty', 'blank', 'oversized'])
def test_api_rejects_invalid_text(text):
    assert TestClient(app).post('/analyze/text', json={'text': text}).status_code == 422


def test_fusion_does_not_invent_emotions_for_unknown_text(monkeypatch):
    from app.services.fusion import fuse_emotion
    from app.services.baseline_delta import FeatureDelta
    result = project_six(native(**{'없음': 0.9}))
    monkeypatch.setattr('app.services.fusion.get_text_emotion_classifier',
                        lambda: SimpleNamespace(classify=lambda text: result))
    fusion = fuse_emotion('오늘은 월요일', {'pitchMean': FeatureDelta('pitchMean', 1, 3, 2, 2)}, {})
    assert fusion.emotion_keywords == []
    assert fusion.emotion_intensity == 0


def test_step2_reports_model_unavailability(monkeypatch):
    def fail(*args):
        raise TextEmotionUnavailable('model missing')
    monkeypatch.setattr('app.api.routes.step2.extract_voice_features', lambda data: {})
    monkeypatch.setattr('app.api.routes.step2.extract_face_features', lambda data: {})
    monkeypatch.setattr('app.api.routes.step2.compute_voice_delta', lambda *args: {})
    monkeypatch.setattr('app.api.routes.step2.compute_face_delta', lambda *args: {})
    monkeypatch.setattr('app.api.routes.step2.fuse_emotion', fail)
    response = TestClient(app).post('/diary/step2/analyze', data={'text': '행복하다'},
                                   files={'voice_file': ('voice.wav', b'test'), 'face_image': ('face.png', b'test')})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'text_emotion_unavailable'
