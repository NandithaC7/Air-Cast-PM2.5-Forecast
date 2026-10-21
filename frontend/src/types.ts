import type { KnownPipelineStatus } from "./config";

export type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "not_configured"; message: string }
  | { status: "not_connected"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

export interface Station {
  location_id: number;
  name: string;
  city: string | null;
  provider: string | null;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
}

export interface StationsResponse {
  stations: Station[];
}

export interface Observation {
  timestamp: string;
  location_id: number;
  station_name: string | null;
  pm25: number | null;
  unit: string | null;
  valid: boolean | null;
}

export interface ObservationsResponse {
  station_id: number;
  unit: string | null;
  page: number;
  page_size: number;
  total: number;
  items: Observation[];
}

export interface DailyPoint {
  date: string;
  pm25_daily_mean: number | null;
  valid_hours: number | null;
  exceeds: number | null;
}

export interface LatestObservation {
  timestamp: string | null;
  pm25: number | null;
  unit: string | null;
}

export interface LatestDailyMean {
  date: string | null;
  pm25_daily_mean: number | null;
  valid_hours: number | null;
  exceeds: number | null;
}

export interface Freshness {
  latest_observation_at: string | null;
  coverage_start: string | null;
  coverage_end: string | null;
}

export interface QualitySummary {
  valid_readings: number | null;
  invalid_readings: number | null;
  missing_hours: number | null;
  expected_hours: number | null;
  latest_timestamp: string | null;
  missing_hour_timestamps: string[] | null;
}

export interface SummaryResponse {
  station_id: number;
  unit: string | null;
  threshold_ug_m3: number | null;
  min_hours_per_day: number | null;
  latest_observation: LatestObservation | null;
  latest_daily_mean: LatestDailyMean | null;
  first_feature_date: string | null;
  latest_feature_date: string | null;
  freshness: Freshness | null;
  quality: QualitySummary | null;
  daily_series: DailyPoint[];
}

export interface PipelineStage {
  id: string;
  status: KnownPipelineStatus | string;
  detail: string | null;
  last_success_at: string | null;
  latest_observation_at: string | null;
  records: number | null;
  last_error: string | null;
  last_processing_run_at: string | null;
}

export interface PipelineResponse {
  generated_at: string | null;
  stages: PipelineStage[];
}

export interface ModelIdentity {
  name: string | null;
  version: string | null;
  training_period: { start: string | null; end: string | null } | null;
}

export interface ForecastResponse {
  station_id: number;
  available: boolean;
  reason: string | null;
  input_date: string | null;
  input_data_timestamp: string | null;
  target_date: string | null;
  pm25_input_daily_mean: number | null;
  unit: string | null;
  hazard_class: "hazard" | "no_hazard" | null;
  probability: number | null;
  probability_supported: boolean;
  threshold_ug_m3: number | null;
  decision_threshold: number | null;
  model: ModelIdentity | null;
}

export interface ConfusionMatrix {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}

export interface ScoreBlock {
  precision: number | null;
  recall: number | null;
  f1: number | null;
  pr_auc: number | null;
  auc_roc: number | null;
  n: number | null;
  confusion: ConfusionMatrix | null;
}

export interface BaselineBlock {
  description: string | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  pr_auc: number | null;
  confusion: ConfusionMatrix | null;
  model_precision_at_baseline_recall: number | null;
}

export interface MetricsResponse {
  available: boolean;
  reason: string | null;
  model: ModelIdentity | null;
  threshold_ug_m3: number | null;
  decision_threshold: number | null;
  target_recall: number | null;
  test: ScoreBlock | null;
  baseline: BaselineBlock | null;
}

export type ModelKey = "logistic_regression" | "decision_tree" | "random_forest" | "linear_svm";

export interface OverviewResponse {
  stations: number;
  labelled_station_days: number;
  hazard_positive: number;
  hazard_negative: number;
  valid_hourly_observations: number;
  eligible_station_days: number;
  first_feature_date: string;
  last_feature_date: string;
  latest_observation_date: string | null;
  hazard_threshold_ug_m3: number;
  preferred_model: string | null;
  preferred_display_name: string | null;
  selection_criterion: string | null;
}

export interface ComparisonRow {
  model: string;
  display_name: string;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  accuracy: number | null;
  preferred: boolean;
}

export interface RuntimeRow {
  model: string;
  display_name: string;
  train_seconds: number;
  predict_seconds: number;
}

export interface CurvePointBlock {
  score_kind: string | null;
  roc: { false_positive_rate: number[]; true_positive_rate: number[]; auc: number | null } | null;
  pr: { precision: number[]; recall: number[]; average_precision: number | null; prevalence: number | null } | null;
  roc_unavailable_reason: string | null;
  pr_unavailable_reason: string | null;
}

export interface AttributionItem {
  feature: string;
  value: number;
}

export interface ChartsResponse {
  comparison: ComparisonRow[];
  confusion: Record<string, ConfusionMatrix & { normalization: string }>;
  curves: Record<string, CurvePointBlock>;
  feature_attribution: Record<string, { kind: string; note?: string; items: AttributionItem[] }>;
  runtime: RuntimeRow[];
  temporal_trend: { date: string; daily_mean_pm25: number; stations: number; exceeds_threshold: number; series_kind: string }[];
  error_analysis: Record<string, { station: string; n: number; false_positives: number; false_negatives: number; true_positives: number; true_negatives: number }[]>;
}

export interface ModelCard {
  name: string;
  display_name: string;
  available: boolean;
  preferred: boolean;
}

export interface PredictV1Response {
  available: boolean;
  reason: string | null;
  station_id: number | null;
  station: string | null;
  input_date: string | null;
  input_data_timestamp?: string | null;
  target_date: string | null;
  pm25_input_daily_mean: number | null;
  unit: string | null;
  hazard_class: "hazard" | "no_hazard" | null;
  predicted_class: number | null;
  interpretation: string | null;
  probability: number | null;
  probability_supported: boolean;
  decision_score: number | null;
  score_kind: string | null;
  threshold_ug_m3: number | null;
  decision_threshold: number | null;
  model: ModelIdentity | null;
}
