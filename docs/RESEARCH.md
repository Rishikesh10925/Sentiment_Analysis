# Research methodology and measured results

This document reports **only what was measured in this repository**. Every
number is stored in `results/research/*.json` together with the script that
produced it. Where a result is weak, contradictory or unflattering, it is
reported that way; nothing here is a projected or "expected" figure.

## 1. Questions

- **Q1** How well does a cheap, CPU-servable linear model handle 3-class social
  media sentiment, and what does the extra accuracy of a stronger linear model
  cost?
- **Q2** Do the usual preprocessing and class-balancing choices actually help on
  this data?
- **Q3** What does a CPU-only transformer fine-tune achieve within a realistic
  budget, and does it beat the linear baseline?
- **Q4** Are the token attributions shown in the UI faithful to the model?
- **Q5** Does aspect-level polarity transfer across product domains?
- **Q6** Where does PySpark time actually go on 1.6M rows — the Python UDF, or
  the shuffle configuration?

## 2. Data and splits

| Corpus | Size used | Labels | Role |
| --- | --- | --- | --- |
| Sentiment140 (`BrianLeung/sentiment140-csv`) | 1,598,315 posts | Distant binary (emoticon-derived) | Dashboard corpus |
| GoEmotions raw | 48,501 Reddit comments | 27 emotions → 3-way polarity | Dashboard corpus |
| TweetEval sentiment | 45,615 train / 12,284 test | 3-class human labels | Model comparison (Q1–Q3) |
| SemEval-2014 Task 4 (restaurants + laptops) | 5,921 train / 1,758 test aspect terms | 3-class per aspect | ABSA (Q5) |

Details:

- The dashboard corpus is the union above after deduplication and schema
  normalisation: **1,646,816 rows**, 2009-04-06 → 2019-02-01, 17 rule-based
  topics. Hashes and counts: `data/curated/manifest.json`.
- TweetEval's official train/test split is used unchanged. The test split is
  never trained on.
- SemEval-2014 uses the official train/test split. Input is
  `sentence [ASPECT] term [ASPECT] term`; repeating the term gives the linear
  model an anchor. **Aspect terms are given at test time**, so this measures
  polarity classification, not aspect extraction.
- Domain shift is evaluated on 20,000-post samples of the dashboard corpus,
  comparing model predictions against the corpus gold polarity. It is a
  *behavioural* check on unlabelled-for-this-task data, not a clean benchmark.

## 3. Methods

### 3.1 Linear baselines

Scikit-learn pipelines, seed 42, `class_weight="balanced"` unless stated:

| Arm | Features | Model |
| --- | --- | --- |
| `majority` | — | Most frequent class |
| `tfidf_multinomial_nb` | word 1–2 grams | Multinomial NB |
| `tfidf_complement_nb` | word 1–2 grams | Complement NB |
| `tfidf_linear_svc` | word 1–2 grams | Linear SVC |
| `tfidf_logreg` | word 1–2 grams | Logistic regression (**deployed**) |
| `tfidf_word_char_logreg` | word 1–2 + char_wb 3–5 grams | Logistic regression (**best**) |

Minimum normalisation only (URL/mention/hashtag tokens mapped to placeholders,
whitespace collapsed). Ablations then vary one choice at a time.

### 3.2 Transformer

`distilbert-base-uncased`, `max_len=64`, batch 64, lr 3e-5, 2 epochs, CPU
(24 threads). No GPU was available: CUDA wheel installs failed repeatedly with
network/`WinError 32` interruptions, so the run is CPU-only and its training
budget is small by design. Reported with training time and per-epoch validation
so the budget is visible.

### 3.3 ABSA

Word 1–2 + char_wb 3–5 gram TF-IDF, class-balanced logistic regression on the
combined restaurants+laptops training set. Evaluated on the combined test set
and per domain, plus both cross-domain directions (train on one domain, test on
the other).

### 3.4 Explainability

The serving model is linear, so an exact per-token attribution exists:
`tfidf_value × coefficient[class]`, summed to the decision margin. This is what
the UI's explanation drawer shows.

Faithfulness is measured, not assumed:

1. **Deletion test** on 150 held-out TweetEval rows. Remove the top-3 attributed
   tokens and measure the drop in the predicted class probability; repeat with
   three random tokens as a control.
2. **LIME agreement** on 60 rows: top-5 token Jaccard overlap between exact
   linear SHAP and LIME. LIME is an independent, perturbation-based
   approximation, so agreement is descriptive evidence, not ground truth.

### 3.5 Spark benchmark

Three arms, same input projection (cached) and same aggregate — count per
platform × topic × predicted sentiment — at 100k, 500k and 1.6M rows:

| Arm | Cleaning | AQE | Shuffle partitions | Pruning |
| --- | --- | --- | --- | --- |
| `naive` | Python UDF | off | 200 | none |
| `native` | SQL expressions | off | 200 | none |
| `optimized` | SQL expressions | on | 2 × cores | before aggregation |

Median of three repetitions per cell, plus a partition sweep at 1.6M rows.

### 3.6 Statistics

- 1,000-sample bootstrap 95% CIs for macro-F1 on the test set.
- Expected calibration error (10 equal-width bins) and Brier score for
  probability quality. ECE is computed on the multiclass confidence of the
  predicted class.

## 4. Results

### 4.1 Linear baselines (TweetEval test, n = 12,284)

| Model | Accuracy | Macro-F1 | Weighted-F1 | Train (s) |
| --- | --- | --- | --- | --- |
| Majority | 0.4833 | 0.2172 | 0.3150 | 0.01 |
| Multinomial NB | 0.5578 | 0.5029 | 0.5210 | 2.26 |
| Complement NB | 0.5660 | 0.5661 | 0.5655 | 2.25 |
| Linear SVC | 0.5913 | 0.5846 | 0.5916 | 2.92 |
| **Logistic regression (deployed)** | **0.5856** | **0.5816** | 0.5862 | 8.92 |
| Word + char logistic regression | 0.6088 | **0.6055** | 0.6092 | 21.80 |

Bootstrap 95% CI for the deployed model: **0.5728 – 0.5902**; for word+char:
**0.5966 – 0.6139**. The intervals do not overlap, so the word+char gain
(+0.024 macro-F1) is larger than test-sampling noise.

Calibration: deployed ECE **0.0784**, Brier 0.5358; word+char ECE **0.1015**,
Brier 0.5223. The more accurate model is less calibrated — the two objectives
are not the same, which is why the UI shows confidence rather than treating it
as certainty.

Interpretation: the deployed model is within 0.024 macro-F1 of the best linear
configuration while training in 9 s instead of 22 s and keeping attribution
exact and cheap. That is the trade-off that justified serving it.

### 4.2 Ablations (against the deployed word-1–2 logistic regression)

| Change | Macro-F1 | Δ |
| --- | --- | --- |
| Baseline | 0.5816 | — |
| Aggressive stopword/punctuation cleaning | 0.5627 | **−0.0189** |
| Unigrams only (no bigrams) | 0.5737 | −0.0079 |
| Remove class weighting | 0.5728 | −0.0088 |

The usual "clean the text harder" instinct *hurts* here: negation and short
social-media cues survive minimum normalisation but not aggressive cleaning.
Class weighting and bigrams both contribute, modestly.

### 4.3 Learning curve (deployed configuration)

| Train rows | Macro-F1 | Accuracy |
| --- | --- | --- |
| 4,561 (10%) | 0.5093 | 0.5221 |
| 11,403 (25%) | 0.5479 | 0.5552 |
| 22,807 (50%) | 0.5688 | 0.5730 |
| 45,615 (100%) | 0.5850 | 0.5891 |

Still rising at 100% of the training split (the 0.5850 here differs slightly
from 0.5816 in §4.1 because this curve uses a single fixed subsample protocol).
A linear model has not saturated, which is one argument for the transformer —
but the transformer's own budget in this environment is the limiting factor.

### 4.4 Transformer fine-tune (CPU)

<!-- TRANSFORMER_RESULTS -->

### 4.5 Domain shift: TweetEval model on the dashboard corpora

20,000 posts per platform, predictions vs corpus gold polarity. "Coverage" is
the share of rows where the model committed to a polarity **and** the gold label
is polar; accuracy is reported only on those rows, so abstentions are visible
rather than hidden.

| Corpus | Model neutral rate | Coverage | Accuracy on covered | Macro-F1 on covered | Rows |
| --- | --- | --- | --- | --- | --- |
| X/Twitter (Sentiment140) | 0.2547 | 0.7452 | 0.7290 | 0.7273 | 14,905 |
| Reddit (GoEmotions) | 0.2264 | 0.4925 | 0.7985 | 0.7930 | 9,850 |

Two readings matter:

1. Accuracy on covered rows (~0.73–0.80) is **not** comparable to the 0.586
   TweetEval accuracy, because the hard neutral rows are excluded. Quoting the
   higher number as "accuracy on real data" would be misleading.
2. Sentiment140's labels are emoticon-derived. A 0.73 agreement is evidence the
   model learned *something* transferable, not that either label source is
   correct.

### 4.6 Aspect-based sentiment (SemEval-2014)

| Setting | n | Accuracy | Macro-F1 | 95% CI |
| --- | --- | --- | --- | --- |
| Majority | 1,758 | 0.6081 | 0.2521 | 0.2464 – 0.2579 |
| Combined domains | 1,758 | **0.7110** | **0.6106** | — |
| Restaurants only | 1,120 | 0.7277 | 0.5992 | 0.5632 – 0.6308 |
| Laptops only | 638 | 0.6818 | 0.6211 | 0.5799 – 0.6590 |
| Restaurants → laptops | 638 | 0.5690 | 0.4657 | — |
| Laptops → restaurants | 1,120 | 0.6080 | 0.4191 | — |

Cross-domain macro-F1 drops by roughly 0.15–0.20 against in-domain. Zero-shot
domain transfer of aspect polarity is the hard part; the neutral class is the
main casualty in both directions.

### 4.7 Explanation faithfulness

150 examples, top-3 deletion:

| Measure | Value |
| --- | --- |
| Mean probability drop, top-3 tokens | **0.3876** |
| Mean probability drop, 3 random tokens | −0.0476 |
| Faithfulness gap | **0.4353** |
| Share of examples where top-3 beats random | **97.33%** |

LIME agreement (60 examples): mean top-5 Jaccard **0.3241**, any overlap
**86.67%**. The attributions are clearly tied to model behaviour under
deletion; the modest exact overlap with LIME shows that two valid explanation
methods disagree on *which* of several correlated tokens to credit. Both facts
are shown to the user, and the deletion caveat (removing a token also changes
TF-IDF normalisation) is stated in the UI and in the payload's `limitations`.

### 4.8 Spark scaling

<!-- SPARK_RESULTS -->

### 4.9 Operational throughput

| Operation | Measured |
| --- | --- |
| Bulk scoring of the 1.65M-row corpus | 81.96 s → **20,094 rows/s** (CPU, batch 100k) |
| ABSA inference (1,758 aspect terms) | 0.306 s → 174 ms/1k rows |
| Prediction distribution (dashboard) | Negative 518,525 · Neutral 416,465 · Positive 711,826 |

## 5. Threats to validity

- **Label noise.** Sentiment140 labels are emoticon-derived and binary; the
  dashboard's 3-way distribution is a model output over that corpus, not an
  annotation of it. GoEmotions is collapsed from 27 emotions to 3 classes by a
  documented rule.
- **Single split.** All test numbers come from one split per dataset. Bootstrap
  CIs cover test sampling only, not training variance. No cross-validation was
  run for the linear models.
- **Ablations share the test set.** The ablation table is descriptive and was
  not used for model selection; nevertheless those comparisons have no held-out
  confirmation split.
- **Transformer budget.** CPU-only, 2 epochs, `max_len=64`. Any comparison
  against published transformer results is invalid; the only fair comparison is
  against the linear baselines measured here under the same split.
- **Rules, not classifiers.** Topics come from keyword rules (82% of posts land
  in `General`), so topic-level aggregates are coarse.
- **Explanations.** Attribution measures model behaviour. Deletion perturbs
  TF-IDF normalisation. LIME is itself approximate. Neither is causal evidence
  about authors or real-world effects.
- **Spark numbers are single-node wall-clock** on one Windows machine with a
  local JVM. They are a reproducibility record, not a distributed claim, and
  they are not comparable to cluster benchmarks.
- **Serving latency** is batch throughput; single-request API latency is
  dominated by request overhead and was not separately benchmarked.

## 6. Reproduction

```bash
python -m research.baselines            # §4.1–4.3, §4.5
python -m research.transformer_model --epochs 2 --batch-size 64 --max-len 64
python -m research.absa                 # §4.6
python -m research.explainability       # §4.7
python -m research.benchmark --repeats 3  # §4.8
python -m scripts.predict_curated       # §4.9
```

Environment for the reported runs: Python 3.12.10, Windows 11, 24 logical
cores, no GPU. Library versions are pinned in `requirements.txt` and
`requirements-research.txt`; each artifact records the versions it used.

## 7. Artifact index

| File | Contents |
| --- | --- |
| `results/research/baselines.json` | All six baselines, ablations, learning curve, domain shift, coefficients, error examples |
| `results/research/baselines_summary.json` | Compact metric table |
| `results/research/transformer.json` | DistilBERT metrics, history, confusion matrix, calibration, latency, error examples |
| `results/research/external_twitter_roberta.json` | Zero-shot Cardiff Twitter-RoBERTa evaluation (if run) |
| `results/research/absa.json` | Per-domain, combined and cross-domain ABSA metrics |
| `results/research/explainability.json` | Deletion test, LIME agreement, example attributions |
| `results/research/spark_benchmark.json` | Three-arm scaling benchmark, environment, partition sweep |
| `results/research/bulk_inference.json` | Full-corpus scoring throughput and distribution |
| `results/research/db_load.json` | Postgres row counts and alert values after load |
| `data/curated/manifest.json` | Corpus provenance, SHA-256, row counts, topic distribution |
