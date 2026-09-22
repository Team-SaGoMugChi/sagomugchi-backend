import numpy as np
import pytest

from app.services.kote_emotion import EXPECTED_LABELS
from scripts.evaluate_kote import evaluate_predictions, metrics, read_split


def test_multilabel_metrics_count_false_positives_and_misses():
    result = metrics([[1, 0], [0, 1], [0, 0]], [[1, 1], [0, 0], [0, 0]], ['a', 'b'])
    assert result['macro_f1'] == pytest.approx(0.5)
    assert result['micro_f1'] == pytest.approx(0.5)
    assert result['exact_match'] == pytest.approx(1 / 3)
    assert result['hamming_loss'] == pytest.approx(2 / 6)


def test_tsv_has_no_header_and_preserves_quoted_multiline_text():
    rows = read_split('first\t"첫 줄\n둘째 줄"\t0,43\n'.encode('utf-8'))
    assert rows == [('first', '첫 줄\n둘째 줄', [0, 43])]


@pytest.mark.parametrize('content', [b'id\ttext\t44', b'id\ttext\t0\nid\tother\t1'])
def test_invalid_dataset_is_rejected(content):
    with pytest.raises(ValueError):
        read_split(content)


def test_six_proxy_merges_gold_synonyms_and_counts_abstentions_as_misses():
    labels = sorted(EXPECTED_LABELS)
    gold = np.zeros((2, 44), dtype=bool)
    gold[:, labels.index('기쁨')] = True
    gold[0, labels.index('행복')] = True
    scores = np.zeros((2, 44))
    scores[0, labels.index('기쁨')] = 0.4
    scores[1, labels.index('기쁨')] = 0.39
    result = evaluate_predictions(gold, scores, labels)['six_class_proxy']
    assert result['per_label']['기쁨']['support'] == 2
    assert result['per_label']['기쁨']['recall'] == 0.5
    assert result['abstention_count'] == 1
    assert result['top1_in_mapped_gold_rate'] == 0.5
