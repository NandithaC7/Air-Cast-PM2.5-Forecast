/**
 * Project settings that already exist in the Scala and PySpark stages.
 * These are configuration, not measurements and not model output.
 */
export const PROJECT_THRESHOLD_UG_M3 = 60;
export const PROJECT_MIN_HOURS_PER_DAY = 18;
export const PROJECT_TIMEZONE = "Asia/Kolkata";

const rawBase = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL = typeof rawBase === "string" ? rawBase.trim().replace(/\/+$/, "") : "";

/** Compact dashboard flow. Status still comes from GET /api/pipeline/status. */
export const INGESTION_FLOW = [
  { id: "openaq_api", title: "OpenAQ" },
  { id: "ingestion", title: "Ingestion" },
  { id: "validation", title: "Validation" },
  { id: "pyspark", title: "Daily aggregation" },
  { id: "forecast_api", title: "Forecast" },
] as const;

export const KNOWN_PIPELINE_STATUSES = [
  "connected",
  "running",
  "completed",
  "delayed",
  "failed",
  "not_configured",
] as const;

export type KnownPipelineStatus = (typeof KNOWN_PIPELINE_STATUSES)[number];
