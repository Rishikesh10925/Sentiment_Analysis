"""Fine-tuned transformer baseline + external pretrained comparison.

The environment used for the reported run has no CUDA-enabled PyTorch build,
so the fine-tuning loop is deliberately small and CPU-friendly: DistilBERT,
max sequence length 64, batch size 64, two epochs, class-weighted loss.
The script works unchanged on CUDA if ``torch.cuda.is_available()``.

Reported artifacts
------------------
models/research/distilbert_tweet_eval/      fine-tuned checkpoint + tokenizer
results/research/transformer.json           metrics, history, runtime
results/research/predictions/distilbert_test.parquet
results/research/external_twitter_roberta.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    get_linear_schedule_with_warmup,
)

from research.config import LABELS, RESEARCH_MODELS_DIR, RESEARCH_RESULTS_DIR, SEED
from research.data import load_tweet_eval
from research.metrics import (
    bootstrap_ci,
    classification_report,
    error_examples,
    expected_calibration_error,
    save_json,
)
from research.text import normalise

PREDICTIONS_DIR = RESEARCH_RESULTS_DIR / "predictions"
BASE_MODEL = "distilbert-base-uncased"
EXTERNAL_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
LABEL2ID = {label: i for i, label in enumerate(LABELS)}


class TextDataset(Dataset):
    def __init__(self, encodings, labels=None):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx):
        item = {key: torch.tensor(value[idx]) for key, value in self.encodings.items()}
        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def _threads() -> int:
    return max(1, min(24, os.cpu_count() or 1))


def _tokenize(tokenizer, texts, max_len: int):
    return tokenizer(
        list(texts), truncation=True, max_length=max_len,
        padding=False, return_tensors=None,
    )


@torch.no_grad()
def predict_texts(model, tokenizer, texts, max_len=64, batch_size=64, device="cpu"):
    model.eval()
    encodings = _tokenize(tokenizer, texts, max_len)
    ds = TextDataset(encodings)
    loader = DataLoader(ds, batch_size=batch_size, collate_fn=DataCollatorWithPadding(tokenizer))
    probs, preds = [], []
    start = time.perf_counter()
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        logits = model(**batch).logits
        batch_probs = torch.softmax(logits, dim=-1).cpu().numpy()
        probs.append(batch_probs)
        preds.extend(batch_probs.argmax(axis=1).tolist())
    elapsed = time.perf_counter() - start
    return np.vstack(probs), [LABELS[i] for i in preds], elapsed


def train_transformer(max_train: int | None = None, epochs: int = 2, batch_size: int = 64,
                      lr: float = 3e-5, max_len: int = 64, output_dir: Path | None = None) -> dict:
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(_threads())
    device = "cuda" if torch.cuda.is_available() else "cpu"
    output_dir = output_dir or (RESEARCH_MODELS_DIR / "distilbert_tweet_eval")

    splits = load_tweet_eval()
    train, validation, test = splits["train"], splits["validation"], splits["test"]
    if max_train:
        train = train.sample(min(max_train, len(train)), random_state=SEED).reset_index(drop=True)

    train_texts = train["text"].map(normalise)
    val_texts = validation["text"].map(normalise)
    test_texts = test["text"].map(normalise)
    y_train = np.array([LABEL2ID[y] for y in train["label"]])
    y_val = np.array([LABEL2ID[y] for y in validation["label"]])
    y_test = np.array([LABEL2ID[y] for y in test["label"]])

    print(f"Device: {device} | torch threads: {torch.get_num_threads()} | train rows: {len(train)}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=3, id2label={i: l for i, l in enumerate(LABELS)},
        label2id=LABEL2ID,
    ).to(device)

    train_ds = TextDataset(_tokenize(tokenizer, train_texts, max_len), y_train)
    val_ds = TextDataset(_tokenize(tokenizer, val_texts, max_len), y_val)
    collator = DataCollatorWithPadding(tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collator)
    val_loader = DataLoader(val_ds, batch_size=batch_size, collate_fn=collator)

    counts = np.bincount(y_train, minlength=3)
    weights = torch.tensor((counts.sum() / (3 * counts)), dtype=torch.float, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * 0.1), total_steps)

    history = []
    best_f1 = -1.0
    best_state = None
    train_start = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for step, batch in enumerate(train_loader, start=1):
            batch = {k: v.to(device) for k, v in batch.items()}
            labels = batch.pop("labels")
            logits = model(**batch).logits
            loss = loss_fn(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            running_loss += loss.item()
            if step % 100 == 0:
                print(f"  epoch {epoch + 1} step {step}/{len(train_loader)} loss={running_loss / step:.4f}", flush=True)
        avg_loss = running_loss / max(len(train_loader), 1)

        model.eval()
        val_probs, val_preds_idx = [], []
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                probs = torch.softmax(model(**batch).logits, dim=-1).cpu().numpy()
                val_probs.append(probs)
                val_preds_idx.extend(probs.argmax(axis=1).tolist())
        val_preds = [LABELS[i] for i in val_preds_idx]
        val_true = [LABELS[i] for i in y_val]
        val_f1 = classification_report(val_true, val_preds)["macro_f1"]
        history.append({"epoch": epoch + 1, "train_loss": round(avg_loss, 4), "val_macro_f1": val_f1})
        print(f"Epoch {epoch + 1}: loss={avg_loss:.4f} val_macro_f1={val_f1}", flush=True)
        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    train_seconds = time.perf_counter() - train_start
    if best_state is not None:
        model.load_state_dict(best_state)
    model.to(device)

    probs, preds, inference_seconds = predict_texts(model, tokenizer, test_texts, max_len=max_len, device=device)
    y_true = [LABELS[i] for i in y_test]
    metrics = classification_report(y_true, preds)
    metrics["bootstrap_macro_f1"] = bootstrap_ci(y_true, preds, metric="macro_f1")
    metrics["calibration"] = expected_calibration_error(y_true, probs)
    metrics["train_seconds"] = round(train_seconds, 2)
    metrics["inference_seconds"] = round(inference_seconds, 2)
    metrics["latency_ms_per_1k"] = round(inference_seconds / len(test_texts) * 1000 * 1000, 2)
    metrics["device"] = device
    metrics["base_model"] = BASE_MODEL
    metrics["epochs"] = epochs
    metrics["max_len"] = max_len
    metrics["batch_size"] = batch_size
    metrics["train_rows"] = int(len(train))
    metrics["history"] = history
    metrics["error_examples"] = error_examples(test_texts.values, y_true, preds, confidences=probs.max(axis=1))

    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    save_json(RESEARCH_RESULTS_DIR / "transformer.json", metrics)

    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    payload = pd.DataFrame({"text": test_texts.values, "gold": y_true, "predicted": preds})
    for i, label in enumerate(LABELS):
        payload[f"prob_{label.lower()}"] = probs[:, i]
    payload.to_parquet(PREDICTIONS_DIR / "distilbert_test.parquet", index=False)
    print(f"Test macro-F1: {metrics['macro_f1']} | accuracy: {metrics['accuracy']}")
    print(f"Saved fine-tuned model -> {output_dir}")
    return metrics


def evaluate_external(max_test: int | None = None) -> dict:
    """Evaluate CardiffNLP's public Twitter RoBERTa checkpoint zero-shot."""
    torch.set_num_threads(_threads())
    device = "cuda" if torch.cuda.is_available() else "cpu"
    splits = load_tweet_eval()
    test = splits["test"]
    if max_test:
        test = test.sample(min(max_test, len(test)), random_state=SEED).reset_index(drop=True)
    texts = test["text"].map(normalise)
    y_true = test["label"].tolist()

    tokenizer = AutoTokenizer.from_pretrained(EXTERNAL_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(EXTERNAL_MODEL).to(device)
    probs, preds, elapsed = predict_texts(model, tokenizer, texts, max_len=128, device=device)
    metrics = classification_report(y_true, preds)
    metrics["bootstrap_macro_f1"] = bootstrap_ci(y_true, preds, metric="macro_f1")
    metrics["calibration"] = expected_calibration_error(y_true, probs)
    metrics["inference_seconds"] = round(elapsed, 2)
    metrics["latency_ms_per_1k"] = round(elapsed / len(test) * 1000 * 1000, 2)
    metrics["model"] = EXTERNAL_MODEL
    metrics["fine_tuned_on_tweet_eval"] = False
    metrics["device"] = device
    metrics["error_examples"] = error_examples(texts.values, y_true, preds, confidences=probs.max(axis=1))
    save_json(RESEARCH_RESULTS_DIR / "external_twitter_roberta.json", metrics)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    payload = pd.DataFrame({"text": texts.values, "gold": y_true, "predicted": preds})
    for i, label in enumerate(LABELS):
        payload[f"prob_{label.lower()}"] = probs[:, i]
    payload.to_parquet(PREDICTIONS_DIR / "external_roberta_test.parquet", index=False)
    print(f"External model macro-F1: {metrics['macro_f1']} | accuracy: {metrics['accuracy']}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-train", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-len", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--external-only", action="store_true")
    parser.add_argument("--skip-external", action="store_true")
    args = parser.parse_args()
    if not args.external_only:
        train_transformer(args.max_train, args.epochs, args.batch_size, args.lr, args.max_len)
    if not args.skip_external:
        evaluate_external()


if __name__ == "__main__":
    main()
