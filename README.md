# AirCast India

**Next-Day PM2.5 Hazard Forecasting**

AirCast India predicts whether a monitoring station is likely to see a next-day PM2.5 hazard, using real OpenAQ-derived hourly observations from 14 Indian stations. A positive label means the following local calendar day's daily mean PM2.5 exceeds a **project-configured** threshold of 60 µg/m³. That threshold is not presented here as an officially verified Indian regulatory cutoff.

```mermaid
flowchart LR
  A[OpenAQ PM2.5 archive] --> B[PySpark cleaning and daily aggregation]
  B --> C[Next-day labels]
  C --> D[Leakage-safe features]
  D --> E[Chronological split]
  E --> F[Four Spark MLlib models]
  F --> G[Evaluation JSON and plots]
  G --> H[FastAPI /api/v1]
  H --> I[React dashboard]
```

Already completed before this implementation: raw expansion, PySpark preprocessing, RDD demonstration, daily aggregation, labels, and feature engineering.

Newly implemented: four-model training and evaluation, artifact persistence, FastAPI, and frontend integration for comparison, charts, and live prediction.

## Architecture

| Layer | Role |
| --- | --- |
| `data/raw/` | Expanded OpenAQ hourly PM2.5 observations |
| `scripts/` | Preprocessing, RDD demo, feature engineering, training |
| `preprocessed/expanded/` | Spark CSV outputs, including `model_features/` |
| `models/` | Spark pipelines plus `inference_bundle.json` |
| `outputs/model_evaluation/` | Metrics, comparison table, chart JSON, PNG plots |
| `backend/` | FastAPI service |
| `frontend/` | Existing Vite + React + TypeScript dashboard |

MongoDB is optional and unused by default. The application runs without it; prediction history is not persisted.

## Dataset

Active source: `data/raw/aircast_pm25_hourly_expanded.csv` and the expanded Spark outputs. The archived original dataset under `archive/original_run/` is provenance only.

Feature columns written by `scripts/aircast_feature_engineering.py`:

`sensor_id`, `station`, `local_date`, `valid_reading_count`, `daily_mean_pm25`, `daily_min_pm25`, `daily_max_pm25`, `pm25_lag1`, `pm25_lag2`, `pm25_lag3`, `pm25_roll7`, `pm25_delta1`, `month_sin`, `month_cos`, `is_winter`, `dow`, `label`

Local calendar convention: `Asia/Kolkata`.

A previously recorded preprocessing report had 117,891 raw hours, 117,768 valid hours, 4,835 eligible station-days, and 4,666 labelled rows (3,018 / 1,648). Recalculate from the files rather than treating those counts as frozen.

## Models

All four classifiers are PySpark MLlib estimators on the same features and the same chronological split:

1. Logistic Regression — L2, 100 iterations, features scaled on the training partition, validation-tuned probability threshold.
2. Decision Tree — Gini, max depth 6, min instances 8.
3. Random Forest — 40 trees, sqrt feature subset, max depth 6.
4. Linear SVM — LinearSVC, L2, scaled features. No calibrated probability; ROC/PR use the decision function.

Missing lag and rolling values are **not** dropped. A mean imputer and missingness indicators are fit on training rows only.

## Split and selection

Unique `local_date` values are split 70% / 15% / 15% in time. Rows that share a calendar date stay in one partition.

**Selection criterion (declared before test inspection):** highest validation-set hazard-class F1, then validation recall, then estimator simplicity (`logistic_regression`, `decision_tree`, `linear_svm`, `random_forest`). The test set is not used to pick the model or the threshold.

Baselines: persistence (today's exceedance predicts tomorrow) and majority class.

## Commands

Python 3.11, Java 17, and a virtual environment are required for Spark.

```bash
# macOS
brew install openjdk@17
export JAVA_HOME="$(brew --prefix openjdk@17)"
export PATH="$JAVA_HOME/bin:$PATH"
export SPARK_LOCAL_IP=127.0.0.1

/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/validate_environment.py
# Existing preprocessing (already run; scripts refuse to overwrite features)
# python scripts/aircast_preprocess_expanded.py
# python scripts/aircast_feature_engineering.py
python scripts/train_and_evaluate_models.py

# API
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Website
cd frontend
cp .env.example .env   # VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Tests:

```bash
source .venv/bin/activate
pytest
cd frontend && npm run build
```

Training writes a versioned run under `outputs/model_evaluation/runs/<id>/` and `models/runs/<id>/`, then updates the active snapshot used by the API. Previous runs are kept.

## API

See [docs/API.md](docs/API.md). Interactive docs: `http://127.0.0.1:8000/docs`.

Environment variables are listed in `.env.example`. Never put an OpenAQ key in the frontend.

## Frontend pages

| Route | Page |
| --- | --- |
| `/` | Overview dashboard |
| `/data` | Air-quality explorer |
| `/models` | Four-model comparison and interactive charts |
| `/forecast` | Working prediction form |
| `/methodology` | Target, split, and model notes |

The website reads live API data. It does not fall back to fake metrics when the backend is down.

## Limitations

- Local Spark on one machine is not a multi-node cluster.
- 60 µg/m³ is a project setting.
- Linear SVM scores are not probabilities.
- Results support further experimentation, not an operational deployment claim.
- Station coverage is uneven; error counts should be read with that in mind.

## Measured holdout results

Chronological split of 635 unique dates:

| Partition | Dates | Rows | Hazard / none | Prevalence |
| --- | --- | --- | --- | --- |
| Train | 2025-01-01 to 2026-03-22 | 2,375 | 1,430 / 945 | 60.2% |
| Validation | 2026-03-23 to 2026-06-25 | 1,231 | 151 / 1,080 | 12.3% |
| Test | 2026-06-26 to 2026-09-29 | 1,060 | 67 / 993 | 6.3% |

The later test window is much less hazardous than the winter-heavy training window. That shift is a dataset property, not a bug.

Test-set metrics after validation-only threshold and model selection:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC | Preferred |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | 0.944 | 0.700 | 0.209 | 0.322 | 0.922 | 0.525 | |
| Decision Tree | 0.951 | 0.615 | 0.597 | 0.606 | 0.893 | 0.517 | |
| Random Forest | 0.945 | 0.563 | 0.597 | 0.580 | 0.913 | 0.541 | |
| Linear SVM | 0.946 | 0.586 | 0.507 | 0.544 | 0.923 | 0.541 | Yes |

Linear SVM was preferred because it had the highest **validation** F1 (0.560). Decision Tree later scored higher on the untouched test set; that does not change the predeclared rule. Linear SVM ROC/PR use the decision function, not a probability.

These scores do not justify operational deployment. Missed summer hazards and false alarms remain material, and class prevalence changes sharply across seasons.

Full numbers: `outputs/model_evaluation/model_metrics.json`.
