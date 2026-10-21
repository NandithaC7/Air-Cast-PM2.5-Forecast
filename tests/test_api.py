from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aircast.paths import latest_evaluation_payload
from backend.app.main import app

client = TestClient(app)
ARTIFACTS = latest_evaluation_payload()


def test_health_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not ARTIFACTS.exists(), reason="Train models before API artifact tests.")
def test_ready_and_model_list():
    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    listing = client.get("/api/v1/models")
    names = {row["name"] for row in listing.json()["models"]}
    assert names == {"logistic_regression", "decision_tree", "random_forest", "linear_svm"}


@pytest.mark.skipif(not ARTIFACTS.exists(), reason="Train models before API artifact tests.")
def test_metrics_are_not_placeholders():
    payload = client.get("/api/v1/models/metrics").json()
    for name in ("logistic_regression", "decision_tree", "random_forest", "linear_svm"):
        test = payload["models"][name]["test"]
        assert test["n"] > 0
        assert test["tp"] + test["tn"] + test["fp"] + test["fn"] == test["n"]
        assert 0 <= test["accuracy"] <= 1


@pytest.mark.skipif(not ARTIFACTS.exists(), reason="Train models before API artifact tests.")
def test_unknown_model_and_invalid_predict():
    assert client.get("/api/v1/models/not-a-model").status_code == 404
    bad = client.post("/api/v1/predict", json={"model_name": "not-a-model", "sensor_id": 1})
    assert bad.status_code in {404, 422}
    missing = client.post("/api/v1/predict", json={"model_name": "logistic_regression"})
    assert missing.status_code == 422


@pytest.mark.skipif(not ARTIFACTS.exists(), reason="Train models before API artifact tests.")
def test_valid_prediction_uses_saved_artifact():
    stations = client.get("/api/v1/stations").json()["stations"]
    assert stations
    station_id = stations[0]["location_id"]
    response = client.post(
        "/api/v1/predict",
        json={"model_name": "logistic_regression", "station_id": station_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["hazard_class"] in {"hazard", "no_hazard"}
    assert body["model"]["name"] == "logistic_regression"
    if not body["probability_supported"]:
        assert body["probability"] is None


def test_prediction_history_explains_missing_database():
    response = client.get("/api/v1/predictions/history")
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert "MongoDB" in body["reason"]
