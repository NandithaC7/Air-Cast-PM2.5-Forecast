import { KNOWN_PIPELINE_STATUSES } from "../config";
import type {
  BaselineBlock,
  ConfusionMatrix,
  DailyPoint,
  ForecastResponse,
  Freshness,
  LatestDailyMean,
  LatestObservation,
  MetricsResponse,
  ModelIdentity,
  Observation,
  ObservationsResponse,
  PipelineResponse,
  PipelineStage,
  QualitySummary,
  ScoreBlock,
  Station,
  StationsResponse,
  SummaryResponse,
} from "../types";

function fail(label: string): never {
  throw new Error(`Response is missing a valid ${label}.`);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) fail(label);
  return value as Record<string, unknown>;
}

function key(obj: Record<string, unknown>, name: string): unknown {
  if (!(name in obj)) fail(name);
  return obj[name];
}

function nullableString(value: unknown, label: string): string | null {
  if (value === null) return null;
  if (typeof value === "string") return value;
  fail(label);
}

function nullableNumber(value: unknown, label: string): number | null {
  if (value === null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  fail(label);
}

function nullableInt(value: unknown, label: string): number | null {
  const parsed = nullableNumber(value, label);
  if (parsed === null) return null;
  if (!Number.isInteger(parsed)) fail(label);
  return parsed;
}

function requiredInt(value: unknown, label: string): number {
  if (typeof value === "number" && Number.isInteger(value)) return value;
  fail(label);
}

function requiredString(value: unknown, label: string): string {
  if (typeof value === "string" && value.length > 0) return value;
  fail(label);
}

function nullableBool(value: unknown, label: string): boolean | null {
  if (value === null) return null;
  if (typeof value === "boolean") return value;
  fail(label);
}

function requiredBool(value: unknown, label: string): boolean {
  if (typeof value === "boolean") return value;
  fail(label);
}

function station(value: unknown, index: number): Station {
  const row = record(value, `stations[${index}]`);
  return {
    location_id: requiredInt(key(row, "location_id"), "location_id"),
    name: requiredString(key(row, "name"), "name"),
    city: nullableString(key(row, "city"), "city"),
    provider: nullableString(key(row, "provider"), "provider"),
    latitude: nullableNumber(key(row, "latitude"), "latitude"),
    longitude: nullableNumber(key(row, "longitude"), "longitude"),
    timezone: nullableString(key(row, "timezone"), "timezone"),
  };
}

export function parseStations(data: unknown): StationsResponse {
  const body = record(data, "stations response");
  const list = key(body, "stations");
  if (!Array.isArray(list)) fail("stations");
  return { stations: list.map(station) };
}

function observation(value: unknown, index: number): Observation {
  const row = record(value, `items[${index}]`);
  return {
    timestamp: requiredString(key(row, "timestamp"), "timestamp"),
    location_id: requiredInt(key(row, "location_id"), "location_id"),
    station_name: nullableString(key(row, "station_name"), "station_name"),
    pm25: nullableNumber(key(row, "pm25"), "pm25"),
    unit: nullableString(key(row, "unit"), "unit"),
    valid: nullableBool(key(row, "valid"), "valid"),
  };
}

export function parseObservations(data: unknown): ObservationsResponse {
  const body = record(data, "observations response");
  const list = key(body, "items");
  if (!Array.isArray(list)) fail("items");
  return {
    station_id: requiredInt(key(body, "station_id"), "station_id"),
    unit: nullableString(key(body, "unit"), "unit"),
    page: requiredInt(key(body, "page"), "page"),
    page_size: requiredInt(key(body, "page_size"), "page_size"),
    total: requiredInt(key(body, "total"), "total"),
    items: list.map(observation),
  };
}

function dailyPoint(value: unknown, index: number): DailyPoint {
  const row = record(value, `daily_series[${index}]`);
  return {
    date: requiredString(key(row, "date"), "date"),
    pm25_daily_mean: nullableNumber(key(row, "pm25_daily_mean"), "pm25_daily_mean"),
    valid_hours: nullableInt(key(row, "valid_hours"), "valid_hours"),
    exceeds: nullableInt(key(row, "exceeds"), "exceeds"),
  };
}

function latestObservation(value: unknown): LatestObservation | null {
  if (value === null) return null;
  const row = record(value, "latest_observation");
  return {
    timestamp: nullableString(key(row, "timestamp"), "timestamp"),
    pm25: nullableNumber(key(row, "pm25"), "pm25"),
    unit: nullableString(key(row, "unit"), "unit"),
  };
}

function latestDaily(value: unknown): LatestDailyMean | null {
  if (value === null) return null;
  const row = record(value, "latest_daily_mean");
  return {
    date: nullableString(key(row, "date"), "date"),
    pm25_daily_mean: nullableNumber(key(row, "pm25_daily_mean"), "pm25_daily_mean"),
    valid_hours: nullableInt(key(row, "valid_hours"), "valid_hours"),
    exceeds: nullableInt(key(row, "exceeds"), "exceeds"),
  };
}

function freshness(value: unknown): Freshness | null {
  if (value === null) return null;
  const row = record(value, "freshness");
  return {
    latest_observation_at: nullableString(key(row, "latest_observation_at"), "latest_observation_at"),
    coverage_start: nullableString(key(row, "coverage_start"), "coverage_start"),
    coverage_end: nullableString(key(row, "coverage_end"), "coverage_end"),
  };
}

function quality(value: unknown): QualitySummary | null {
  if (value === null) return null;
  const row = record(value, "quality");
  const missing = key(row, "missing_hour_timestamps");
  if (missing !== null && !Array.isArray(missing)) fail("missing_hour_timestamps");
  return {
    valid_readings: nullableInt(key(row, "valid_readings"), "valid_readings"),
    invalid_readings: nullableInt(key(row, "invalid_readings"), "invalid_readings"),
    missing_hours: nullableInt(key(row, "missing_hours"), "missing_hours"),
    expected_hours: nullableInt(key(row, "expected_hours"), "expected_hours"),
    latest_timestamp: nullableString(key(row, "latest_timestamp"), "latest_timestamp"),
    missing_hour_timestamps:
      missing === null ? null : missing.map((item, index) => requiredString(item, `missing_hour_timestamps[${index}]`)),
  };
}

export function parseSummary(data: unknown): SummaryResponse {
  const body = record(data, "summary response");
  const series = key(body, "daily_series");
  if (!Array.isArray(series)) fail("daily_series");
  return {
    station_id: requiredInt(key(body, "station_id"), "station_id"),
    unit: nullableString(key(body, "unit"), "unit"),
    threshold_ug_m3: nullableNumber(key(body, "threshold_ug_m3"), "threshold_ug_m3"),
    min_hours_per_day: nullableInt(key(body, "min_hours_per_day"), "min_hours_per_day"),
    latest_observation: latestObservation(key(body, "latest_observation")),
    latest_daily_mean: latestDaily(key(body, "latest_daily_mean")),
    first_feature_date: "first_feature_date" in body ? nullableString(key(body, "first_feature_date"), "first_feature_date") : null,
    latest_feature_date: "latest_feature_date" in body ? nullableString(key(body, "latest_feature_date"), "latest_feature_date") : null,
    freshness: freshness(key(body, "freshness")),
    quality: quality(key(body, "quality")),
    daily_series: series.map(dailyPoint),
  };
}

function stage(value: unknown, index: number): PipelineStage {
  const row = record(value, `stages[${index}]`);
  const status = requiredString(key(row, "status"), "status").toLowerCase();
  const known = (KNOWN_PIPELINE_STATUSES as readonly string[]).includes(status);
  return {
    id: requiredString(key(row, "id"), "id"),
    status: known ? status : requiredString(key(row, "status"), "status"),
    detail: nullableString(key(row, "detail"), "detail"),
    last_success_at: nullableString(key(row, "last_success_at"), "last_success_at"),
    latest_observation_at: nullableString(key(row, "latest_observation_at"), "latest_observation_at"),
    records: nullableInt(key(row, "records"), "records"),
    last_error: nullableString(key(row, "last_error"), "last_error"),
    last_processing_run_at: nullableString(key(row, "last_processing_run_at"), "last_processing_run_at"),
  };
}

export function parsePipeline(data: unknown): PipelineResponse {
  const body = record(data, "pipeline response");
  const list = key(body, "stages");
  if (!Array.isArray(list)) fail("stages");
  return {
    generated_at: nullableString(key(body, "generated_at"), "generated_at"),
    stages: list.map(stage),
  };
}

function modelIdentity(value: unknown): ModelIdentity | null {
  if (value === null) return null;
  const row = record(value, "model");
  const period = key(row, "training_period");
  let training: ModelIdentity["training_period"] = null;
  if (period !== null) {
    const span = record(period, "training_period");
    training = {
      start: nullableString(key(span, "start"), "training_period.start"),
      end: nullableString(key(span, "end"), "training_period.end"),
    };
  }
  return {
    name: nullableString(key(row, "name"), "model.name"),
    version: nullableString(key(row, "version"), "model.version"),
    training_period: training,
  };
}

function hazardClass(value: unknown): ForecastResponse["hazard_class"] {
  if (value === null) return null;
  if (value === "hazard" || value === "no_hazard") return value;
  fail("hazard_class");
}

export function parseForecast(data: unknown): ForecastResponse {
  const body = record(data, "forecast response");
  const supported = requiredBool(key(body, "probability_supported"), "probability_supported");
  const probability = nullableNumber(key(body, "probability"), "probability");
  if (supported && probability === null) fail("probability");
  if (!supported && probability !== null) fail("probability");
  return {
    station_id: requiredInt(key(body, "station_id"), "station_id"),
    available: requiredBool(key(body, "available"), "available"),
    reason: nullableString(key(body, "reason"), "reason"),
    input_date: nullableString(key(body, "input_date"), "input_date"),
    input_data_timestamp: nullableString(key(body, "input_data_timestamp"), "input_data_timestamp"),
    target_date: nullableString(key(body, "target_date"), "target_date"),
    pm25_input_daily_mean: nullableNumber(key(body, "pm25_input_daily_mean"), "pm25_input_daily_mean"),
    unit: nullableString(key(body, "unit"), "unit"),
    hazard_class: hazardClass(key(body, "hazard_class")),
    probability,
    probability_supported: supported,
    threshold_ug_m3: nullableNumber(key(body, "threshold_ug_m3"), "threshold_ug_m3"),
    decision_threshold: nullableNumber(key(body, "decision_threshold"), "decision_threshold"),
    model: modelIdentity(key(body, "model")),
  };
}

function confusion(value: unknown): ConfusionMatrix | null {
  if (value === null) return null;
  const row = record(value, "confusion");
  return {
    tp: requiredInt(key(row, "tp"), "tp"),
    fp: requiredInt(key(row, "fp"), "fp"),
    fn: requiredInt(key(row, "fn"), "fn"),
    tn: requiredInt(key(row, "tn"), "tn"),
  };
}

function scoreBlock(value: unknown): ScoreBlock | null {
  if (value === null) return null;
  const row = record(value, "test");
  return {
    precision: nullableNumber(key(row, "precision"), "precision"),
    recall: nullableNumber(key(row, "recall"), "recall"),
    f1: nullableNumber(key(row, "f1"), "f1"),
    pr_auc: nullableNumber(key(row, "pr_auc"), "pr_auc"),
    auc_roc: nullableNumber(key(row, "auc_roc"), "auc_roc"),
    n: nullableInt(key(row, "n"), "n"),
    confusion: confusion(key(row, "confusion")),
  };
}

function baseline(value: unknown): BaselineBlock | null {
  if (value === null) return null;
  const row = record(value, "baseline");
  return {
    description: nullableString(key(row, "description"), "description"),
    precision: nullableNumber(key(row, "precision"), "precision"),
    recall: nullableNumber(key(row, "recall"), "recall"),
    f1: nullableNumber(key(row, "f1"), "f1"),
    pr_auc: nullableNumber(key(row, "pr_auc"), "pr_auc"),
    confusion: confusion(key(row, "confusion")),
    model_precision_at_baseline_recall: nullableNumber(
      key(row, "model_precision_at_baseline_recall"),
      "model_precision_at_baseline_recall",
    ),
  };
}

export function parseMetrics(data: unknown): MetricsResponse {
  const body = record(data, "metrics response");
  return {
    available: requiredBool(key(body, "available"), "available"),
    reason: nullableString(key(body, "reason"), "reason"),
    model: modelIdentity(key(body, "model")),
    threshold_ug_m3: nullableNumber(key(body, "threshold_ug_m3"), "threshold_ug_m3"),
    decision_threshold: nullableNumber(key(body, "decision_threshold"), "decision_threshold"),
    target_recall: nullableNumber(key(body, "target_recall"), "target_recall"),
    test: scoreBlock(key(body, "test")),
    baseline: baseline(key(body, "baseline")),
  };
}
