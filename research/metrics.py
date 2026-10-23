"""Evaluation utilities: bootstrap intervals, McNemar, calibration, reports.

All functions are deterministic given a seed and return JSON-serialisable
Python types so results can be committed alongside the code.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from research.config import LABELS, SEED


def classification_report(y_true, y_pred, labels=None) -> dict:
    """Macro + weighted metrics, per-class metrics and a confusion matrix."""
    labels = labels or LABELS
    p, r, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "per_class": {
            label: {
                "precision": round(float(p[i]), 4),
                "recall": round(float(r[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "confusion_matrix_labels": list(labels),
    }


def bootstrap_ci(y_true, y_pred, metric: str = "macro_f1", n_boot: int = 1000,
                 seed: int = SEED, labels=None) -> dict:
    """Percentile bootstrap 95% CI for accuracy / macro_f1 / weighted_f1."""
    labels = labels or LABELS
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    rng = np.random.default_rng(seed)

    def score(yt, yp):
        if metric == "accuracy":
            return accuracy_score(yt, yp)
        if metric == "macro_f1":
            return f1_score(yt, yp, labels=labels, average="macro", zero_division=0)
        if metric == "weighted_f1":
            return f1_score(yt, yp, labels=labels, average="weighted", zero_division=0)
        raise ValueError(f"Unsupported metric: {metric}")

    n = len(y_true)
    values = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        values.append(score(y_true[idx], y_pred[idx]))
    values = np.asarray(values)
    return {
        "metric": metric,
        "mean": round(float(values.mean()), 4),
        "ci95_low": round(float(np.percentile(values, 2.5)), 4),
        "ci95_high": round(float(np.percentile(values, 97.5)), 4),
        "n_boot": n_boot,
    }


def mcnemar_test(y_true, pred_a, pred_b) -> dict:
    """Exact binomial McNemar test on paired predictions (two-sided)."""
    y_true = np.asarray(y_true)
    a_correct = np.asarray(pred_a) == y_true
    b_correct = np.asarray(pred_b) == y_true
    b = int(np.sum(a_correct & ~b_correct))  # a right, b wrong
    c = int(np.sum(~a_correct & b_correct))  # a wrong, b right
    n = b + c
    if n == 0:
        p_value = 1.0
    else:
        k = min(b, c)
        # two-sided exact binomial test, p=0.5
        tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
        p_value = min(1.0, 2 * tail)
    return {
        "a_only_correct": b,
        "b_only_correct": c,
        "n_discordant": n,
        "p_value": round(float(p_value), 6),
        "significant_05": bool(p_value < 0.05),
    }


def expected_calibration_error(y_true, probabilities, labels=None, n_bins: int = 10) -> dict:
    """ECE + reliability bins for multiclass probabilities."""
    labels = labels or LABELS
    probabilities = np.asarray(probabilities, dtype=float)
    label_to_idx = {label: i for i, label in enumerate(labels)}
    y_idx = np.array([label_to_idx[y] for y in y_true])
    conf = probabilities.max(axis=1)
    pred_idx = probabilities.argmax(axis=1)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    reliability = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        acc = float((pred_idx[mask] == y_idx[mask]).mean())
        avg_conf = float(conf[mask].mean())
        ece += mask.mean() * abs(acc - avg_conf)
        reliability.append({
            "bin_low": round(float(lo), 2),
            "bin_high": round(float(hi), 2),
            "count": int(mask.sum()),
            "avg_confidence": round(avg_conf, 4),
            "accuracy": round(acc, 4),
        })
    return {
        "ece": round(float(ece), 4),
        "brier": round(float(np.mean(np.sum((probabilities - np.eye(len(labels))[y_idx]) ** 2, axis=1))), 4),
        "reliability": reliability,
    }


def error_examples(texts, y_true, y_pred, confidences=None, limit: int = 25) -> list:
    """Most confident mistakes, useful for qualitative error analysis."""
    rows = []
    for i, (text, gold, pred) in enumerate(zip(texts, y_true, y_pred)):
        if gold == pred:
            continue
        rows.append({
            "text": str(text),
            "gold": str(gold),
            "predicted": str(pred),
            "confidence": round(float(confidences[i]), 4) if confidences is not None else None,
        })
    rows.sort(key=lambda r: (r["confidence"] or 0), reverse=True)
    return rows[:limit]


def save_json(path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
