"""Reproducible held-out KOTE evaluation; no training or threshold tuning.

Run from backend root: python -m scripts.evaluate_kote
Downloaded comments and per-item scores stay in ignored .cache; reports contain
aggregates only. The six-label gold is mechanically mapped, not independently
annotated Oddo ground truth.
"""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import time
from datetime import datetime, timezone

import numpy as np
import requests

from app.services.kote_emotion import (
    KoteTextEmotionClassifier, MODEL_ID, MODEL_REVISION, MAPPING_VERSION,
    SIX_EMOTION_GROUPS, project_six,
)
from app.services.text_emotion import EMOTION_LABELS

DATA_REVISION = 'cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977'
SOURCE = f'https://raw.githubusercontent.com/searle-j/KOTE/{DATA_REVISION}'


def metrics(gold, predicted, labels):
    gold, predicted = np.asarray(gold, bool), np.asarray(predicted, bool)
    if gold.shape != predicted.shape or gold.ndim != 2 or gold.shape[1] != len(labels) or not len(gold):
        raise ValueError('nonempty matching multilabel matrices required')
    tp = (gold & predicted).sum(axis=0)
    fp = (~gold & predicted).sum(axis=0)
    fn = (gold & ~predicted).sum(axis=0)

    def ratio(a, b):
        return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b != 0)

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    f1 = ratio(2 * tp, 2 * tp + fp + fn)
    micro_denominator = int(2 * tp.sum() + fp.sum() + fn.sum())
    return {
        'count': len(gold), 'macro_f1': float(f1.mean()),
        'micro_f1': float(2 * tp.sum() / micro_denominator) if micro_denominator else 0.0,
        'exact_match': float((gold == predicted).all(axis=1).mean()),
        'hamming_loss': float((gold != predicted).mean()),
        'per_label': {label: {'precision': float(precision[i]), 'recall': float(recall[i]),
                              'f1': float(f1[i]), 'support': int(gold[:, i].sum()),
                              'tp': int(tp[i]), 'fp': int(fp[i]), 'fn': int(fn[i])}
                      for i, label in enumerate(labels)},
    }


def read_split(content):
    rows = []
    for row in csv.reader(io.StringIO(content.decode('utf-8')), delimiter='\t'):
        if len(row) != 3:
            raise ValueError('Unexpected TSV schema')
        indices = [int(label) for label in row[2].split(',')]
        if not indices or any(not 0 <= label < 44 for label in indices):
            raise ValueError('Unexpected label ID')
        rows.append((row[0], row[1], indices))
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError('Duplicate IDs within split')
    return rows


def load_splits(cache):
    cache.mkdir(parents=True, exist_ok=True)
    splits, hashes = {}, {}
    for name, count in [('train', 40000), ('val', 5000), ('test', 5000)]:
        path = cache / f'{name}.tsv'
        if not path.exists():
            response = requests.get(f'{SOURCE}/{name}.tsv', timeout=60)
            response.raise_for_status()
            rows = read_split(response.content)
            if len(rows) != count:
                raise ValueError('Unexpected split count')
            path.write_bytes(response.content)
        content = path.read_bytes()
        splits[name] = read_split(content)
        if len(splits[name]) != count:
            raise ValueError('Unexpected cached split count')
        hashes[name] = hashlib.sha256(content).hexdigest()
    return splits, hashes


def evaluate_predictions(gold, scores, labels):
    if scores.shape != gold.shape or not np.isfinite(scores).all() or (scores < 0).any() or (scores > 1).any():
        raise ValueError('Invalid predictions')
    report = {'native_44': {str(t): metrics(gold, scores >= t, labels) for t in (0.3, 0.4)}}
    six_gold = np.array([
        gold[:, [labels.index(source) for source in SIX_EMOTION_GROUPS[label]]].any(axis=1)
        for label in EMOTION_LABELS
    ]).T
    results = [project_six(dict(zip(labels, row)), threshold=0.4) for row in scores]
    six_pred = np.array([[r.scores[label] > 0 for label in EMOTION_LABELS] for r in results])
    six = metrics(six_gold, six_pred, EMOTION_LABELS)
    covered = six_gold.any(axis=1)
    abstained = np.array([r.dominant_emotion is None for r in results])
    hits = [bool(six_gold[i, EMOTION_LABELS.index(r.dominant_emotion)])
            if r.dominant_emotion is not None else False for i, r in enumerate(results)]
    six.update({
        'gold_source': 'OR of existing KOTE gold labels using oddo-six-v1; NOT independent six-class labels',
        'threshold': 0.4, 'mapping_version': MAPPING_VERSION,
        'abstention_count': int(abstained.sum()), 'abstention_rate': float(abstained.mean()),
        'mapped_gold_count': int(covered.sum()), 'unmapped_only_gold_count': int((~covered).sum()),
        'top1_in_mapped_gold_rate': float(np.array(hits)[covered].mean()) if covered.any() else None,
        'top1_denominator': int(covered.sum()),
        'top1_definition': 'Dominant prediction belongs to mapped gold set; abstentions count as misses; not single-label accuracy',
    })
    report['six_class_proxy'] = six
    return report


def write_markdown(report, path):
    native = report['native_44']
    six = report['six_class_proxy']
    lines = ['# KOTE 공식 시험셋 평가', '',
             f"- 평가 건수: {report['samples']:,}건 (공식 test.tsv 전체)",
             f"- 모델: `{MODEL_ID}` / `{MODEL_REVISION}`",
             f"- 데이터 버전: `{DATA_REVISION}`",
             '- 학습 및 시험셋을 이용한 문턱값 조정 없음. 문턱값 0.3/0.4를 사전 지정.',
             '- 6종은 동일 대응표로 정답을 변환한 참고 평가이며 오또 실사용 정확도가 아님.', '',
             '| 평가 | Macro F1 | Micro F1 | 정답 집합 완전 일치 |',
             '|---|---:|---:|---:|']
    for name, result in [('44종 / 0.3', native['0.3']), ('44종 / 0.4', native['0.4']), ('6종 변환 / 0.4 (참고)', six)]:
        lines.append(f"| {name} | {result['macro_f1']:.4f} | {result['micro_f1']:.4f} | {result['exact_match']:.2%} |")
    lines += ['', 'F1은 정밀도와 재현율을 함께 반영한다. Macro는 감정별 동등 평균, Micro는 전체 판정 합산이다.',
              '완전 일치는 한 문장의 모든 감정 항목을 빠짐없이 맞추고 오탐도 없는 비율이다.', '',
              '## 6종별 참고 성능', '', '| 감정 | 정밀도 | 재현율 | F1 | 정답 포함 문장 수 |', '|---|---:|---:|---:|---:|']
    for label, values in six['per_label'].items():
        lines.append(f"| {label} | {values['precision']:.4f} | {values['recall']:.4f} | {values['f1']:.4f} | {values['support']} |")
    lines += ['', f"- 판단 불가: {six['abstention_count']}건 ({six['abstention_rate']:.2%}).",
              f"- 6종으로 옮길 정답이 있는 문장: {six['mapped_gold_count']}건; 없는 문장: {six['unmapped_only_gold_count']}건.",
              f"- 대표 감정이 정답 집합에 포함된 비율: {six['top1_in_mapped_gold_rate']:.2%} (대상 {six['top1_denominator']}건, 판단 불가는 오답 처리).",
              '- 이 비율은 다중 정답 중 하나만 맞춰도 인정하므로 단일 정답률로 표현하면 안 된다.', '',
              '## 평가 조건과 한계', '',
              f"- 학습/검증과 시험 ID 겹침: {report['overlap']['id_overlap']}건.",
              f"- 학습/검증에 같은 텍스트가 있는 시험 문장: {report['overlap']['exact_text_overlap']}건 (별도 지표는 JSON 참고).",
              f"- 최대 입력 토큰: {report['max_tokens']}; 512토큰 초과 문장: {report['long_inputs']}건.",
              f"- 추론 시간: {report['inference_seconds']:.1f}초, CPU threads={report['threads']} / batch={report['batch_size']}.",
              '- KOTE는 댓글 데이터다. 말하기 일기, STT 오류, 현재 감정 구분에 대한 성능을 대신하지 않는다.',
              '- 6종 정답도 같은 대응표로 만들었으므로 대응표의 심리적 타당성은 검증하지 못한다.',
              '- 원문 댓글과 개별 예측은 Git에 포함하지 않는다. 데이터 SHA256과 전체 라벨 지표는 JSON에 기록했다.',
              '- 다음 단계: 팀원이 독립적으로 표시한 오또 일기 6종 평가셋으로 검증.', '',
              '출처: https://github.com/searle-j/KOTE / https://aclanthology.org/2024.lrec-main.1499/']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--output', type=Path, default=Path('docs/evaluations/kote-test-2026-09-16.json'))
    args = parser.parse_args()
    if args.batch_size < 1 or args.threads < 1:
        parser.error('batch-size and threads must be positive')
    splits, hashes = load_splits(Path('.cache/kote-evaluation') / DATA_REVISION)
    rows = splits['test']
    seen_ids = {r[0] for name in ('train', 'val') for r in splits[name]}
    seen_text = {r[1] for name in ('train', 'val') for r in splits[name]}
    id_overlap = sum(r[0] in seen_ids for r in rows)
    if id_overlap:
        raise ValueError('Test IDs overlap training/validation; refuse evaluation')
    overlap = np.array([r[1] in seen_text for r in rows])

    classifier = KoteTextEmotionClassifier(cache_dir='.cache/kote', local_files_only=True)
    torch, tokenizer, model, labels = classifier._load()
    torch.set_num_threads(args.threads)
    token_lists = tokenizer([r[1] for r in rows], add_special_tokens=False, truncation=False, verbose=False)['input_ids']
    window = model.config.max_position_embeddings - tokenizer.num_special_tokens_to_add(pair=False)
    chunks = [(i, ids[start:start + window]) for i, ids in enumerate(token_lists) for start in range(0, len(ids), window)]
    if any(not ids for ids in token_lists):
        raise ValueError('Empty tokenized test input')
    chunks.sort(key=lambda item: len(item[1]))
    accumulated = np.zeros((len(rows), 44), dtype=np.float64)
    start_time = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(chunks), args.batch_size):
            batch = chunks[start:start + args.batch_size]
            encodings = [tokenizer.prepare_for_model(ids, add_special_tokens=True, return_attention_mask=True)
                         for _, ids in batch]
            inputs = tokenizer.pad(encodings, padding=True, return_tensors='pt')
            values = torch.sigmoid(model(**inputs).logits).cpu().numpy()
            for (index, ids), values_row in zip(batch, values):
                accumulated[index] += values_row * len(ids)
            if start % (args.batch_size * 20) == 0:
                print(f'Processed {min(start + args.batch_size, len(chunks))}/{len(chunks)} chunks; {time.perf_counter()-start_time:.1f}s', flush=True)
    seconds = time.perf_counter() - start_time
    scores = accumulated / np.array([len(ids) for ids in token_lists])[:, None]
    gold = np.zeros_like(scores, dtype=bool)
    for i, row in enumerate(rows):
        gold[i, row[2]] = True
    report = evaluate_predictions(gold, scores, labels)
    report.update({
        'evaluated_at_utc': datetime.now(timezone.utc).isoformat(), 'samples': len(rows),
        'model_id': MODEL_ID, 'model_revision': MODEL_REVISION, 'dataset_revision': DATA_REVISION,
        'data_sha256': hashes, 'batch_size': args.batch_size, 'threads': args.threads,
        'inference_seconds': seconds, 'max_tokens': max(map(len, token_lists)) + 2,
        'long_inputs': sum(len(ids) > window for ids in token_lists),
        'overlap': {'id_overlap': id_overlap, 'exact_text_overlap': int(overlap.sum())},
        'environment': {'python': platform.python_version(), 'torch': torch.__version__, 'cpu': platform.processor()},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limitations': ['Six-class targets are mechanically mapped, not independently annotated.',
                        'Not an Oddo diary/STT benchmark. No threshold optimization on test data.'],
    })
    if overlap.any() and (~overlap).any():
        report['excluding_exact_train_val_text_overlap'] = evaluate_predictions(gold[~overlap], scores[~overlap], labels)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_markdown(report, args.output.with_suffix('.md'))
    np.savez_compressed('.cache/kote-evaluation/test-predictions.npz', scores=scores, gold=gold, labels=labels,
                        ids=[r[0] for r in rows], model_revision=MODEL_REVISION, dataset_revision=DATA_REVISION)
    print(json.dumps({key: report[key] for key in ('samples', 'inference_seconds', 'overlap')}, ensure_ascii=False), flush=True)
    print('Saved ' + str(args.output), flush=True)


if __name__ == '__main__':
    main()
