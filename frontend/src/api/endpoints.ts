import { apiGet, apiPost } from "./client";
import { parseForecast, parseMetrics, parseObservations, parsePipeline, parseStations, parseSummary } from "./parse";
import type {
  ChartsResponse,
  ForecastResponse,
  MetricsResponse,
  ModelCard,
  ObservationsResponse,
  OverviewResponse,
  PipelineResponse,
  PredictV1Response,
  StationsResponse,
  SummaryResponse,
} from "../types";

export interface StationQuery {
  station_id: number;
  from?: string;
  to?: string;
}

export function getStations(): Promise<StationsResponse> {
  return apiGet("api/stations", {}, parseStations);
}

export function getObservations(query: StationQuery & { page: number; page_size: number }): Promise<ObservationsResponse> {
  return apiGet(
    "api/observations",
    {
      station_id: query.station_id,
      from: query.from,
      to: query.to,
      page: query.page,
      page_size: query.page_size,
    },
    parseObservations,
  );
}

export function getSummary(query: StationQuery): Promise<SummaryResponse> {
  return apiGet(
    "api/summary",
    { station_id: query.station_id, from: query.from, to: query.to },
    parseSummary,
  );
}

export function getPipelineStatus(): Promise<PipelineResponse> {
  return apiGet("api/pipeline/status", {}, parsePipeline);
}

export function getForecast(stationId: number, targetDate?: string): Promise<ForecastResponse> {
  return apiGet("api/forecast", { station_id: stationId, target_date: targetDate }, parseForecast);
}

export function getMetrics(stationId: number): Promise<MetricsResponse> {
  return apiGet("api/model/metrics", { station_id: stationId }, parseMetrics);
}

function asRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Response is missing a valid ${label}.`);
  }
  return value as Record<string, unknown>;
}

export function getOverview(): Promise<OverviewResponse> {
  return apiGet("api/v1/overview", {}, (data) => asRecord(data, "overview") as unknown as OverviewResponse);
}

export function getModelCards(): Promise<ModelCard[]> {
  return apiGet("api/v1/models", {}, (data) => {
    const body = asRecord(data, "models");
    if (!Array.isArray(body.models)) throw new Error("Response is missing a valid models list.");
    return body.models as ModelCard[];
  });
}

export function getCharts(): Promise<ChartsResponse> {
  return apiGet("api/v1/charts", {}, (data) => asRecord(data, "charts") as unknown as ChartsResponse);
}

export function getEvaluationMetrics(): Promise<Record<string, unknown>> {
  return apiGet("api/v1/models/metrics", {}, (data) => asRecord(data, "metrics"));
}

export function postPrediction(body: {
  model_name: string;
  station_id: number;
  target_date?: string;
}): Promise<PredictV1Response> {
  return apiPost("api/v1/predict", body, (data) => asRecord(data, "predict") as unknown as PredictV1Response);
}
