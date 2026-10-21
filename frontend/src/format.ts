import { PROJECT_TIMEZONE } from "./config";

const MISSING = "—";

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCount(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  return Math.trunc(value).toLocaleString("en-IN");
}

export function formatMetric(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });
}

export function isMicrogramUnit(unit: string | null | undefined): boolean {
  if (!unit) return false;
  const compact = unit.toLowerCase().replace(/\s+/g, "");
  return compact === "ug/m3" || compact === "µg/m³" || compact === "μg/m3" || compact === "µg/m3";
}

/** Concentration with an explicit unit. Unknown units are shown as the API sent them. */
export function formatConcentration(value: number | null | undefined, unit: string | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  const amount = formatNumber(value, 1);
  if (unit == null || isMicrogramUnit(unit)) return `${amount} µg/m³`;
  return `${amount} ${unit}`;
}

export function formatWhen(value: string | null | undefined): string {
  if (!value) return MISSING;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: PROJECT_TIMEZONE,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(parsed);
  return `${formatted} IST`;
}

export function formatElapsed(value: string | null | undefined, now = Date.now()): string {
  if (!value) return MISSING;
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return MISSING;
  const seconds = Math.max(0, Math.round((now - parsed) / 1000));
  if (seconds < 60) return `${seconds} s since the reported timestamp`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min since the reported timestamp`;
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  if (hours < 48) return `${hours} h ${remMin} min since the reported timestamp`;
  const days = Math.floor(hours / 24);
  return `${days} d ${hours % 24} h since the reported timestamp`;
}

export function hazardLabel(value: "hazard" | "no_hazard" | null | undefined): string {
  if (value === "hazard") return "Hazard";
  if (value === "no_hazard") return "No hazard";
  return "Model not available";
}

export function pipelineStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "connected":
      return "Connected";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "delayed":
      return "Delayed";
    case "failed":
      return "Failed";
    case "not_configured":
      return "Not configured";
    case "awaiting_backend":
      return "Awaiting backend";
    case "loading":
      return "Loading";
    case "not_reported":
      return "Not reported";
    default:
      return status && status.length > 0 ? status : "Not reported";
  }
}

export function statusTone(status: string): "neutral" | "info" | "ok" | "warn" | "bad" {
  if (status === "failed") return "bad";
  if (status === "delayed") return "warn";
  if (status === "running") return "info";
  if (status === "connected" || status === "completed") return "ok";
  return "neutral";
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  return `${(value * 100).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}%`;
}

/** Next calendar date after a YYYY-MM-DD civil date. Used for the next-day forecast target. */
export function addCalendarDay(isoDate: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return null;
  const [year, month, day] = isoDate.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1));
  return next.toISOString().slice(0, 10);
}

export function modelDisplayName(name: string | null | undefined): string {
  if (!name) return "Model not available";
  const key = name.toLowerCase().replace(/[\s-]+/g, "_");
  if (key === "lr" || key === "logistic" || key === "logistic_regression") return "Logistic Regression";
  if (key === "gbt" || key === "gbtclassifier") return "Gradient-boosted trees";
  if (key === "dt" || key === "decision_tree") return "Decision Tree";
  if (key === "rf" || key === "random_forest") return "Random Forest";
  if (key === "svm" || key === "linear_svm" || key === "linearsvc") return "Linear SVM";
  return name;
}

export function exceedsLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return MISSING;
  if (value === 1) return "Above threshold";
  if (value === 0) return "At or below threshold";
  return String(value);
}
