import { useEffect } from "react";
import { getEvaluationMetrics, getOverview } from "../api/endpoints";
import { EndpointState } from "../components/StateMessage";
import { FieldList } from "../components/FieldList";
import { PROJECT_THRESHOLD_UG_M3, PROJECT_TIMEZONE } from "../config";
import { formatCount, formatMetric } from "../format";
import { useRequest } from "../hooks/useRequest";

export function MethodologyPage() {
  const overview = useRequest(() => getOverview(), []);
  const metrics = useRequest(() => getEvaluationMetrics(), []);

  useEffect(() => {
    document.title = "Methodology · AirCast India";
  }, []);

  const split = metrics.state.status === "ready" ? (metrics.state.data.split as Record<string, { first_date?: string; last_date?: string }>) : null;
  const project = metrics.state.status === "ready" ? (metrics.state.data.project as Record<string, string | number>) : null;

  return (
    <div>
      <header className="page-head">
        <h1>Methodology</h1>
        <p className="lede">
          Next-day PM2.5 hazard classification from real OpenAQ-derived observations. A positive label means the
          following local calendar day&apos;s daily mean exceeds a project-configured threshold of {PROJECT_THRESHOLD_UG_M3} µg/m³.
          That threshold is not presented as an officially verified Indian regulatory cutoff.
        </p>
      </header>

      <section className="panel">
        <div className="section-head">
          <h2>Data and target</h2>
        </div>
        <EndpointState state={overview.state} endpoint="GET /api/v1/overview">
          {overview.state.status === "ready" && (
            <FieldList
              items={[
                { label: "Stations", value: formatCount(overview.state.data.stations) },
                { label: "Valid hourly observations", value: formatCount(overview.state.data.valid_hourly_observations) },
                { label: "Labelled station-days", value: formatCount(overview.state.data.labelled_station_days) },
                { label: "Hazard / non-hazard", value: `${formatCount(overview.state.data.hazard_positive)} / ${formatCount(overview.state.data.hazard_negative)}` },
                { label: "Feature date range", value: `${overview.state.data.first_feature_date} to ${overview.state.data.last_feature_date}` },
                { label: "Timezone", value: PROJECT_TIMEZONE },
              ]}
            />
          )}
        </EndpointState>
        <p className="note">
          Features are current-day statistics, calendar-date lags, a 7-day rolling mean, and calendar encodings.
          Future-day measurements and the label are excluded from predictors. Missing lags are retained and imputed
          with training-set means; missingness indicators travel with every model.
        </p>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Chronological evaluation</h2>
        </div>
        <p className="note">
          The primary split is by unique <code>local_date</code> values, not a random row shuffle. All stations on the
          same calendar date stay in one partition so the test set is a later period.
        </p>
        <EndpointState state={metrics.state} endpoint="GET /api/v1/models/metrics">
          {split && (
            <FieldList
              items={[
                { label: "Training dates", value: `${split.train?.first_date ?? "—"} to ${split.train?.last_date ?? "—"}` },
                { label: "Validation dates", value: `${split.validation?.first_date ?? "—"} to ${split.validation?.last_date ?? "—"}` },
                { label: "Test dates", value: `${split.test?.first_date ?? "—"} to ${split.test?.last_date ?? "—"}` },
                { label: "Spark", value: project ? `${project.spark_version} · ${project.spark_mode}` : "Not reported" },
              ]}
            />
          )}
        </EndpointState>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Models</h2>
        </div>
        <ul className="method-list">
          <li>
            <strong>Logistic Regression</strong> — L2-regularized binomial model on scaled features, with a validation-tuned
            probability threshold.
          </li>
          <li>
            <strong>Decision Tree</strong> — Gini tree, depth and leaf-size constrained, validation-tuned probability threshold.
          </li>
          <li>
            <strong>Random Forest</strong> — 40 trees, sqrt feature subset, validation-tuned vote-fraction threshold.
          </li>
          <li>
            <strong>Linear SVM</strong> — LinearSVC on scaled features. No calibrated probability is reported; ranking uses the
            decision function.
          </li>
        </ul>
        <p className="note">
          Imputers and scalers are fit on the training partition only. Class weights are computed from training label
          counts. The preferred model is selected from validation hazard-class F1. These results support further
          experimentation; they are not an operational safety claim.
        </p>
        {metrics.state.status === "ready" && (
          <p className="meta">
            Preferred model F1 on test:{" "}
            {formatMetric(
              ((metrics.state.data.models as Record<string, { test: { f1: number | null } }>)[
                String((metrics.state.data.selection as { preferred_model?: string }).preferred_model)
              ] ?? { test: { f1: null } }
            ).test.f1)}
            .
          </p>
        )}
      </section>
    </div>
  );
}
