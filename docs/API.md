# AirCast India API

Versioned routes live under `/api/v1`. The original frontend routes under `/api` remain as compatibility aliases.

## Health

- `GET /api/v1/health` — process liveness.
- `GET /api/v1/ready` — 200 only when evaluation artifacts and the inference bundle are present.

## Models

- `GET /api/v1/models`
- `GET /api/v1/models/metrics`
- `GET /api/v1/models/comparison`
- `GET /api/v1/models/{model_name}`
- `GET /api/v1/models/{model_name}/confusion-matrix`
- `GET /api/v1/models/{model_name}/curves`
- `GET /api/v1/models/{model_name}/feature-importance`
- `GET /api/v1/overview`
- `GET /api/v1/charts`

`model_name` is one of `logistic_regression`, `decision_tree`, `random_forest`, `linear_svm`.

## Prediction

`POST /api/v1/predict`

```json
{
  "model_name": "logistic_regression",
  "station_id": 23534,
  "target_date": "2026-09-30"
}
```

The backend looks up the station's feature row for the local day before `target_date`. It does not invent missing history. Linear SVM returns `decision_score` and `probability_supported: false`.

`GET /api/v1/predictions/history` reports that history is not persisted unless MongoDB is configured.

## Data

- `GET /api/v1/stations`
- `GET /api/v1/observations?station_id=&from=&to=&page=&page_size=`
- `GET /api/v1/summary?station_id=&from=&to=`
- `GET /api/v1/pipeline/status`

Compatibility: `GET /api/forecast` and `GET /api/model/metrics` serve the preferred model in the original frontend shapes.
