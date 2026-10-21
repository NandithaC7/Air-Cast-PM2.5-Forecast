from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aircast.constants import MODEL_KEYS, MODEL_ORDER
from aircast.paths import evaluation_dir, latest_evaluation_payload, models_dir


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.metrics: dict[str, Any] | None = None
        self.charts: dict[str, Any] | None = None
        self.bundle: dict[str, Any] | None = None
        self.reason: str | None = None
        self.reload()

    def reload(self) -> None:
        metrics_path = latest_evaluation_payload(self.root)
        charts_path = evaluation_dir(self.root) / "charts.json"
        bundle_path = models_dir(self.root) / "inference_bundle.json"
        missing = [str(path) for path in (metrics_path, charts_path, bundle_path) if not path.exists()]
        if missing:
            self.metrics = None
            self.charts = None
            self.bundle = None
            self.reason = "Evaluation artifacts are not available: " + ", ".join(missing)
            return
        self.metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.charts = json.loads(charts_path.read_text(encoding="utf-8"))
        self.bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.reason = None

    @property
    def ready(self) -> bool:
        return self.metrics is not None and self.bundle is not None

    def require(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.ready or self.metrics is None or self.bundle is None:
            raise FileNotFoundError(self.reason or "Model artifacts are not ready.")
        return self.metrics, self.bundle

    def model_status(self) -> list[dict[str, Any]]:
        rows = []
        preferred = None
        if self.metrics:
            preferred = self.metrics.get("selection", {}).get("preferred_model")
        for key in MODEL_ORDER:
            artifact = models_dir(self.root) / key
            rows.append(
                {
                    "name": key,
                    "display_name": MODEL_KEYS[key],
                    "available": artifact.exists() and self.ready,
                    "preferred": key == preferred,
                    "artifact_path": str(artifact.relative_to(self.root)) if artifact.exists() else None,
                }
            )
        return rows
