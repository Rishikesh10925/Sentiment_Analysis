# Signal — social sentiment intelligence

Analytics and research workbench over **1,646,816 real public social posts**
(1,598,315 X/Twitter, 48,501 Reddit; April 2009 – February 2019). A React
dashboard explores the corpus through date/platform/topic filters, explains
individual predictions token by token, and reports the project's measured
model, benchmarking and explainability results — including the ones that did
not go the way the textbook says they should.

The dashboard shows **model predictions, not gold labels**. Gold labels from
the research corpora are kept out of the product surface and used only for
evaluation.

```
X/Twitter (Sentiment140) ─┐
Reddit (GoEmotions)     ──┼─► curation ─► TF-IDF + LR ─► PostgreSQL ─► FastAPI ─► React
TweetEval (eval only)   ──┘        │                              │
SemEval-2014 ABSA (eval only)      └─► PySpark aggregates          └─► /api/v2 (+ SHAP)
```

## Measured results at a glance

All numbers below are produced by the scripts in this repository and stored in
`results/research/`. Full methodology, intervals and limitations:
[`docs/RESEARCH.md`](docs/RESEARCH.md).

| What | Result |
| --- | --- |
| Deployed model (word 1–2 gram TF-IDF + logistic regression) | **0.5816** macro-F1 / 0.5856 accuracy on TweetEval test (n = 12,284) |
| Best linear model (word + char TF-IDF) | **0.6055** macro-F1 / 0.6088 accuracy |
| DistilBERT fine-tune (CPU, 2 epochs) | see `results/research/transformer.json` |
| Aspect-based sentiment (SemEval-2014) | **0.6106** macro-F1 / 0.711 accuracy over 1,758 aspect terms |
| Explanation faithfulness (deletion test, 150 rows) | top-3 token deletion drops target probability by **0.388** vs **−0.048** for random tokens |
| Bulk scoring throughput | 1.65M posts in **82 s** (≈20k rows/s, CPU) |
| Spark benchmark | see `results/research/spark_benchmark.json` (three pipelines, 100k/500k/1.6M rows) |

## What is actually built

- **Real data pipeline** — downloads Sentiment140 and GoEmotions, normalises
  both into one schema, infers 17 topics, records provenance and SHA-256 hashes
  in `data/curated/manifest.json`.
- **Research modules** (`research/`) — reproducible baselines, ablations, a
  learning curve, domain-shift checks, DistilBERT fine-tuning, SemEval-2014
  ABSA, explanation faithfulness (deletion test + LIME agreement), and a
  three-arm Spark benchmark.
- **Serving path** (`ml/serving.py`) — one model artifact used by both the API
  and bulk scoring, with exact linear SHAP attribution (TF-IDF value × class
  coefficient) that needs no second model.
- **Filtered API** (`backend/v2.py`) — summary/trends/platforms/topics/hashtags/
  keywords/posts, per-post detail, prediction + explanation, CSV/PDF export, and
  a research payload assembled from the measured artifacts.
- **Product frontend** — dark editorial UI: overview KPIs and charts, an
  explorer with a model lab and a SHAP drawer, a research/evidence page, alerts,
  and a guarded upload flow.
- **Operations** — API-key-protected uploads, upload size cap, filename
  sanitisation, per-IP rate limiting, structured request logs, short-TTL
  aggregate caching, `/api/ready`, Docker images, GitHub Actions CI, Render
  blueprint.

## Quick start

Requires Python 3.12, Node 22, and Docker (for PostgreSQL). Windows is the
primary development environment for this repository; the commands below are
PowerShell-friendly.

```powershell
# 1. Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

# 2. PostgreSQL (host port 5434)
docker compose up -d db
python -m backend.db.migrate

# 3. Build the corpus (downloads ~1 GB once, then caches)
python -m ingestion.real_data
python -m scripts.predict_curated

# 4. Load 1.65M rows + aggregates into Postgres
python -m backend.db.load_real_data

# 5. API + frontend
uvicorn backend.main:app --reload --port 8000
cd frontend; npm install; npm run dev
```

The dashboard is at <http://localhost:5173>; the API docs (development only) at
<http://localhost:8000/api/docs>.

Already have the parquet corpus and a populated database? Skip step 3 and 4.

## Data

| Source | Rows used | Role | Citation |
| --- | --- | --- | --- |
| [Sentiment140](https://huggingface.co/datasets/BrianLeung/sentiment140-csv) | 1,598,315 | Dashboard corpus (distant binary labels) | Go, Bhayani & Huang (2009) |
| [GoEmotions](https://huggingface.co/datasets/google-research-datasets/go_emotions) | 48,501 | Dashboard corpus (Reddit; 27 emotions → 3-way polarity) | Demszky et al. (2020) |
| [TweetEval sentiment](https://huggingface.co/datasets/cardiffnlp/tweet_eval) | 45,615 train / 12,284 test | Evaluation only | Barbieri et al. (2020) |
| [SemEval-2014 Task 4](https://alt.qcri.org/semeval2014/task4/) | 5,921 train / 1,758 test aspects | ABSA evaluation only | Pontiki et al. (2014) |

Derived parquet files (~170 MB each) are deliberately **not** committed; they
are reproducible with `python -m ingestion.real_data`. Provenance, row counts
and file hashes are in `data/curated/manifest.json`.

Topic labels (`Health`, `Technology`, `Politics`, …) are assigned by keyword
rules, not by a trained classifier. They are a coarse grouping device; see the
limitations section of the research document.

## Models

The deployed model is a word 1–2 gram TF-IDF vectoriser feeding a
class-balanced logistic regression. It is chosen for serving because it scores
~20k posts/second on CPU and produces exact, cheap attributions.

Stronger configurations are measured, not served:

- word + character TF-IDF (0.6055 macro-F1) costs 2.4× the training time and
  complicates attribution;
- DistilBERT is fine-tuned on CPU in this environment, and its measured result,
  including the honest caveat about training budget, is on the Research page.

Reproduce a benchmark:

```bash
python -m research.baselines            # baselines, ablations, learning curve, domain shift
python -m research.transformer_model    # DistilBERT fine-tune + optional external model
python -m research.absa                 # SemEval-2014 aspect-term polarity
python -m research.explainability       # deletion test + LIME agreement
python -m research.benchmark --repeats 3
```

## API

Base path `/api/v2` (see `/api/docs` in development).

| Endpoint | Purpose |
| --- | --- |
| `GET /meta` | Corpus bounds, platforms, topics, model card, provenance |
| `GET /summary`, `/trends`, `/platforms`, `/topics`, `/hashtags`, `/keywords` | Filtered aggregates (`start`, `end`, `platform`, `topic`) |
| `GET /posts`, `/posts/{id}` | Paged explorer results and per-post detail with explanation |
| `GET /alerts` | Threshold alerts computed from the loaded corpus |
| `GET /model`, `/research` | Model card and measured research artifacts |
| `POST /predict`, `/explain` | Score a sentence and attribute it |
| `GET /export/posts.csv`, `/export/report.pdf` | Reproducible exports of the current filter |
| `POST /api/upload` | Validate (and, in the research image, re-analyse) a CSV; protected by `X-API-Key` |

## Tests and CI

```bash
pytest -q                  # backend, data, ML, Spark
cd frontend; npm test      # query/filter helpers (Vitest)
cd frontend; npm run build # type-check + production bundle
```

Two test groups touch the database and are opt-in so the demo corpus is never
overwritten by a test run:

- **Loader tests** (`tests/test_db.py`) reload tables from the sample CSV; they
  only run when `TEST_DATABASE_URL` points at a throwaway database.
- **The full-pipeline upload test** replaces the dashboard tables; run it
  explicitly with `RUN_DESTRUCTIVE_TESTS=1` (it restores the curated corpus
  afterwards).

GitHub Actions runs the backend suite on Python 3.12, the frontend lint/tests/
build on Node 22, and then builds both Docker images and smoke-tests
`/api/health` inside the API container.

## Deployment

Prepared for **Render + Neon**; the blueprint is `render.yaml` and the full
runbook is [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Locally, the production
shape runs with `docker compose up --build` (nginx → API → Postgres).

## Project layout

```
backend/        FastAPI app, v2 API, DB models/session/loaders, observability
research/       Baselines, transformer, ABSA, explainability, Spark benchmark
ml/             Training, bulk prediction, serving + exact SHAP
ingestion/      Real-corpus download/curation and CSV validation
preprocessing/  Text cleaning shared by training and serving
spark/          Native-expression cleaning and aggregate jobs
analytics/      Alert/summary logic
frontend/       React 19 + Vite + Tailwind dashboard
docker/         Backend/frontend Dockerfiles and nginx config
docs/           RESEARCH.md (evidence), DEPLOYMENT.md (Render/Neon runbook)
results/research/  Measured artifacts (JSON) consumed by the Research page
tests/          Backend, data, ML and Spark tests
```

## Limitations

- Sentiment140 labels come from emoticons (distant supervision), not human
  annotation; the dashboard's labels are model predictions over that corpus.
- The 3-class boundary between *Neutral* and everything else is the hardest
  part of the task: neutral recall is the weakest per-class number in every
  model measured here.
- Topic assignment is rule-based and skews toward `General` (82% of posts).
- Explanation attributions describe model behaviour, not author intent.
- The Spark benchmark is single-node and wall-clock; it is a reproducibility
  record, not a distributed-systems claim.
- Uploads that trigger a full re-analysis replace the dashboard tables. The UI
  warns about this and the restore command is shown in the app.

## Attribution

Corpora are used under their respective dataset terms; this repository ships
code and derived artifacts only, not the raw corpora. Cite the original papers
listed in `docs/RESEARCH.md` if you reuse the data or results.
