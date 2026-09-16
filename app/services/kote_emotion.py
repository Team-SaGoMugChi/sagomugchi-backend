"""Pinned KOTE inference and an explicitly heuristic six-emotion adapter.

The 44 independent sigmoid scores are NOT a softmax distribution. Six-class
projection is an Oddo compatibility rule, not a separately trained classifier.
"""

import math
from threading import Lock

from app.services.text_emotion import EMOTION_LABELS, TextEmotionClassifier, TextEmotionResult

MODEL_ID = "searle-j/kote_for_easygoing_people"
MODEL_REVISION = "0d493bc0cbd30923751a1ae7aa34ccfbee08b88d"
MAPPING_VERSION = "oddo-six-v1"
MAX_TEXT_LENGTH = 10000

# Conservative, disjoint groups. Ambiguous labels remain unmapped rather than
# inventing a psychological equivalence (e.g. guilt is not necessarily hurt).
SIX_EMOTION_GROUPS = {
    "기쁨": ("환영/호의", "감동/감탄", "고마움", "기대감", "뿌듯함", "편안/쾌적",
           "아껴주는", "즐거움/신남", "흐뭇함(귀여움/예쁨)", "행복", "기쁨", "안심/신뢰"),
    "슬픔": ("슬픔", "절망", "서러움"),
    "분노": ("불평/불만", "지긋지긋", "화남/분노", "짜증", "증오/혐오"),
    "불안": ("공포/무서움", "불안/걱정", "부담/안_내킴"),
    "상처": ("안타까움/실망", "패배/자기혐오"),
    "당황": ("부끄러움", "어이없음", "당황/난처", "경악", "놀람"),
}
UNMAPPED_LABELS = {
    "존경", "우쭐댐/무시함", "비장함", "의심/불신", "신기함/관심", "한심함",
    "역겨움/징그러움", "귀찮음", "힘듦/지침", "깨달음", "죄책감", "재미없음", "불쌍함/연민",
}
EXPECTED_LABELS = {label for group in SIX_EMOTION_GROUPS.values() for label in group} | UNMAPPED_LABELS | {"없음"}


class TextEmotionUnavailable(RuntimeError):
    """Model/dependency/cache failure; never silently fall back to keywords."""


class TextEmotionInputError(ValueError):
    """User input cannot be processed within the supported limits."""


def project_six(scores: dict[str, float], threshold: float = 0.4) -> TextEmotionResult:
    """Max within each group avoids adding more mass to larger groups.

Reject weak/NO EMOTION-dominated evidence before normalization, which would
otherwise turn a single tiny score into 100% confidence.
"""
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    if set(scores) != EXPECTED_LABELS or any(
        not math.isfinite(value) or not 0 <= value <= 1 for value in scores.values()
    ):
        raise TextEmotionUnavailable("Invalid KOTE score vector")
    grouped = {label: max(scores[key] for key in group) for label, group in SIX_EMOTION_GROUPS.items()}
    strongest = max(grouped.values())
    if strongest < threshold or scores["없음"] >= strongest:
        return TextEmotionResult(dict.fromkeys(EMOTION_LABELS, 0.0), None, 0.0)
    supported = {label: value if value >= threshold else 0.0 for label, value in grouped.items()}
    total = sum(supported.values())
    normalized = {label: value / total for label, value in supported.items()}
    dominant = max(normalized, key=normalized.get)
    # Compatibility field used by fusion, not calibrated certainty/intensity.
    return TextEmotionResult(normalized, dominant, grouped[dominant])


class KoteTextEmotionClassifier(TextEmotionClassifier):
    def __init__(self, *, cache_dir: str | None = None, local_files_only: bool = False,
                 device: str = "cpu", threshold: float = 0.4):
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be cpu or cuda")
        if not 0 < threshold <= 1:
            raise ValueError("threshold must be in (0, 1]")
        self.cache_dir = cache_dir
        self.local_files_only = local_files_only
        self.device = device
        self.threshold = threshold
        self._runtime = None
        # Serializes lazy loading and inference to bound memory per process.
        self._lock = Lock()

    def _load(self):
        if self._runtime is None:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                options = dict(revision=MODEL_REVISION, cache_dir=self.cache_dir,
                               local_files_only=self.local_files_only, trust_remote_code=False)
                tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, **options)
                # Upstream provides only .bin. Restricted weights-only loading;
                # never execute model-repository Python or unpickle arbitrary code.
                model = AutoModelForSequenceClassification.from_pretrained(
                    MODEL_ID, **options, use_safetensors=False, weights_only=True,
                ).to(self.device).eval()
                labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
                if len(labels) != 44 or set(labels) != EXPECTED_LABELS:
                    raise ValueError("Unexpected KOTE labels")
                self._runtime = torch, tokenizer, model, labels
            except Exception as exc:
                raise TextEmotionUnavailable("KOTE could not be loaded; check dependencies/model cache") from exc
        return self._runtime

    def classify(self, text: str) -> TextEmotionResult:
        if not text.strip():
            raise TextEmotionInputError("text must not be blank")
        if len(text) > MAX_TEXT_LENGTH:
            raise TextEmotionInputError(f"text must be at most {MAX_TEXT_LENGTH} characters")
        with self._lock:
            torch, tokenizer, model, labels = self._load()
            try:
                # Do not silently discard the end of a spoken diary at 512 tokens.
                tokens = tokenizer(text, add_special_tokens=False, truncation=False, verbose=False)["input_ids"]
                window = model.config.max_position_embeddings - tokenizer.num_special_tokens_to_add(pair=False)
                if not tokens or window <= 0 or len(tokens) > window * 64:
                    raise TextEmotionInputError("text exceeds supported token range")
                totals = torch.zeros(len(labels), device=self.device)
                with torch.inference_mode():
                    for start in range(0, len(tokens), window):
                        chunk = tokens[start:start + window]
                        inputs = tokenizer.prepare_for_model(
                            chunk, add_special_tokens=True, return_attention_mask=True,
                            return_tensors="pt", prepend_batch_axis=True,
                        ).to(self.device)
                        values = torch.sigmoid(model(**inputs).logits[0])
                        totals += values * len(chunk)
                native = dict(zip(labels, (totals / len(tokens)).cpu().tolist()))
                return project_six(native, self.threshold)
            except TextEmotionInputError:
                raise
            except TextEmotionUnavailable:
                raise
            except Exception as exc:
                raise TextEmotionUnavailable("KOTE inference failed") from exc
