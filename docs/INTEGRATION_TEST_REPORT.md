# AirCast India — Integration Test Report

## Test Environment
- Platform: macOS
- Python: 3.11.16
- pytest: 8.4.2

## Results
- Total tests: 14
- Passed: 14
- Failed: 0

## Test Coverage
- API health, readiness, and model listing
- Model metrics and input validation
- Prediction using the saved inference artifact
- Prediction-history behavior when no database is configured
- Feature schema and binary target validation
- Prevention of future-data and identifier leakage
- Dynamic Spark output discovery
- Chronological train/test split validation
- Confusion metrics, F1, ROC-AUC, and threshold selection
- Inference-bundle round-trip

## Warning
One Starlette deprecation warning was reported concerning httpx and TestClient integration. It did not cause any test failures.

## Limitations
These tests validate the current API, data contract, and inference utilities. They do not independently establish that the four ML models have been freshly trained or that the reported model metrics reproduce from a clean training run.
