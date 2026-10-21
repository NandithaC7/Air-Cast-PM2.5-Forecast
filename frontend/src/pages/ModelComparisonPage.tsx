import { useEffect, useMemo, useState } from "react";
import { getCharts, getEvaluationMetrics, getModelCards } from "../api/endpoints";
import { ConfusionMatrix } from "../components/ConfusionMatrix";
import { ComparisonBars, ImportanceBars, PrChart, RocChart, RuntimeBars, TrendChart } from "../components/EvalCharts";
import { EndpointState } from "../components/StateMessage";
import { FieldList } from "../components/FieldList";
import { formatMetric, modelDisplayName } from "../format";
import { useRequest } from "../hooks/useRequest";

const MODEL_KEYS = ["logistic_regression", "decision_tree", "random_forest", "linear_svm"] as const;

export function ModelComparisonPage() {
  const cards = useRequest(() => getModelCards(), []);
  const charts = useRequest(() => getCharts(), []);
  const metrics = useRequest(() => getEvaluationMetrics(), []);
  const [selected, setSelected] = useState<string>("logistic_regression");

  useEffect(() => {
    document.title = "Model Comparison · AirCast India";
  }, []);

  useEffect(() => {
    if (cards.state.status !== "ready") return;
    const preferred = cards.state.data.find((row) => row.preferred);
    if (preferred) setSelected(preferred.name);
  }, [cards.state]);

  const metricRows = useMemo(() => {
    if (metrics.state.status !== "ready") return [];
    const models = metrics.state.data.models as Record<string, { test: Record<string, number | null>; runtime: { train_seconds: number } }>;
    return MODEL_KEYS.map((key) => {
      const test = models[key]?.test ?? {};
      return {
        key,
        accuracy: test.accuracy,
        precision: test.precision,
        recall: test.recall,
        f1: test.f1,
        macro_f1: test.macro_f1,
        weighted_f1: test.weighted_f1,
        roc_auc: test.roc_auc,
        pr_auc: test.pr_auc,
        train: models[key]?.runtime.train_seconds ?? null,
      };
    });
  }, [metrics.state]);

  const preferred =
    metrics.state.status === "ready"
      ? String((metrics.state.data.selection as { preferred_model?: string })?.preferred_model ?? "")
      : "";
  const criterion =
    metrics.state.status === "ready"
      ? String((metrics.state.data.selection as { criterion?: string })?.criterion ?? "")
      : "";
  const split = metrics.state.status === "ready" ? (metrics.state.data.split as Record<string, unknown>) : null;

  return (
    <div>
      <header className="page-head">
        <h1>Model comparison</h1>
        <p className="lede">
          Four PySpark MLlib classifiers trained on the same leakage-safe features and evaluated on the same
          chronological holdout. The preferred model is chosen from validation F1, not the test set.
        </p>
      </header>

      <EndpointState state={cards.state} endpoint="GET /api/v1/models">
        {cards.state.status === "ready" && (
          <div className="model-grid">
            {cards.state.data.map((card) => (
              <button
                key={card.name}
                type="button"
                className={`model-card ${card.name === selected ? "is-active" : ""} ${card.preferred ? "is-preferred" : ""}`}
                onClick={() => setSelected(card.name)}
              >
                <p className="model-card-name">{card.display_name}</p>
                <p className="meta">{card.available ? "Artifact loaded" : "Artifact missing"}</p>
                {card.preferred && <span className="kind kind-measured">Preferred</span>}
              </button>
            ))}
          </div>
        )}
      </EndpointState>

      {criterion && (
        <section className="panel">
          <div className="section-head">
            <h2>Selection criterion</h2>
          </div>
          <p className="note">{criterion}</p>
          {preferred && <p className="tile-detail">Preferred model after validation: {modelDisplayName(preferred)}.</p>}
        </section>
      )}

      <section className="panel">
        <div className="section-head">
          <h2>Holdout comparison</h2>
          <p>Precision, recall, and F1 are for the next-day hazard class.</p>
        </div>
        <EndpointState state={charts.state} endpoint="GET /api/v1/charts">
          {charts.state.status === "ready" && <ComparisonBars rows={charts.state.data.comparison} />}
        </EndpointState>
        <EndpointState state={metrics.state} endpoint="GET /api/v1/models/metrics">
          {metricRows.length > 0 && (
            <div className="table-wrap">
              <table>
                <caption>Chronological test-set metrics for all four models</caption>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th className="num">Accuracy</th>
                    <th className="num">Precision</th>
                    <th className="num">Recall</th>
                    <th className="num">F1</th>
                    <th className="num">Macro F1</th>
                    <th className="num">Weighted F1</th>
                    <th className="num">ROC-AUC</th>
                    <th className="num">PR-AUC</th>
                    <th className="num">Train (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {metricRows.map((row) => (
                    <tr key={row.key} className={row.key === preferred ? "is-preferred-row" : undefined}>
                      <th scope="row">{modelDisplayName(row.key)}</th>
                      <td className="num">{formatMetric(row.accuracy)}</td>
                      <td className="num">{formatMetric(row.precision)}</td>
                      <td className="num">{formatMetric(row.recall)}</td>
                      <td className="num">{formatMetric(row.f1)}</td>
                      <td className="num">{formatMetric(row.macro_f1)}</td>
                      <td className="num">{formatMetric(row.weighted_f1)}</td>
                      <td className="num">{formatMetric(row.roc_auc)}</td>
                      <td className="num">{formatMetric(row.pr_auc)}</td>
                      <td className="num">{formatMetric(row.train)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </EndpointState>
      </section>

      {split && (
        <section className="panel">
          <div className="section-head">
            <h2>Chronological split</h2>
            <p>Date boundaries are global. Stations that share a calendar date stay in the same partition.</p>
          </div>
          <FieldList
            items={["train", "validation", "test"].map((name) => {
              const span = (split[name] ?? {}) as { first_date?: string; last_date?: string };
              const counts = ((split.label_counts as Record<string, { rows?: number; positive?: number; negative?: number; prevalence?: number }>) ?? {})[name];
              return {
                label: name,
                value: `${span.first_date ?? "—"} to ${span.last_date ?? "—"} · ${counts?.rows ?? "—"} rows · hazard ${counts?.positive ?? "—"} / none ${counts?.negative ?? "—"}`,
              };
            })}
          />
        </section>
      )}

      <section className="panel">
        <div className="section-head">
          <h2>{modelDisplayName(selected)} details</h2>
          <p>Confusion matrix, ranking curves, attribution, and errors for the selected classifier only.</p>
        </div>
        <label className="field">
          <span>Inspect model</span>
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            {MODEL_KEYS.map((key) => (
              <option key={key} value={key}>
                {modelDisplayName(key)}
              </option>
            ))}
          </select>
        </label>
        <EndpointState state={charts.state} endpoint="GET /api/v1/charts">
          {charts.state.status === "ready" && (
            <>
              <h3 className="subhead">Confusion matrix</h3>
              <ConfusionMatrix matrix={charts.state.data.confusion[selected]} />
              <p className="meta">Counts on the chronological test set. Normalization: counts.</p>
              <div className="split">
                <div>
                  <h3 className="subhead">ROC</h3>
                  <RocChart curves={charts.state.data.curves} model={selected} />
                </div>
                <div>
                  <h3 className="subhead">Precision-recall</h3>
                  <PrChart curves={charts.state.data.curves} model={selected} />
                </div>
              </div>
              <h3 className="subhead">Feature attribution</h3>
              <ImportanceBars
                items={charts.state.data.feature_attribution[selected]?.items ?? []}
                kind={charts.state.data.feature_attribution[selected]?.kind ?? "unavailable"}
                note={charts.state.data.feature_attribution[selected]?.note}
              />
              <h3 className="subhead">Station-level errors</h3>
              <div className="table-wrap table-limit">
                <table>
                  <caption>False negatives and false positives by station on the test set</caption>
                  <thead>
                    <tr>
                      <th>Station</th>
                      <th className="num">n</th>
                      <th className="num">FN</th>
                      <th className="num">FP</th>
                      <th className="num">TP</th>
                      <th className="num">TN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(charts.state.data.error_analysis[selected] ?? []).map((row) => (
                      <tr key={row.station}>
                        <td>{row.station}</td>
                        <td className="num">{row.n}</td>
                        <td className="num">{row.false_negatives}</td>
                        <td className="num">{row.false_positives}</td>
                        <td className="num">{row.true_positives}</td>
                        <td className="num">{row.true_negatives}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </EndpointState>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Runtime</h2>
          <p>Measured on the machine that ran the training script. This is a local Spark session, not a cluster.</p>
        </div>
        <EndpointState state={charts.state} endpoint="GET /api/v1/charts">
          {charts.state.status === "ready" && <RuntimeBars rows={charts.state.data.runtime} />}
        </EndpointState>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Historical PM2.5 trend</h2>
          <p>Cross-station mean of measured daily values. Not a model forecast.</p>
        </div>
        <EndpointState state={charts.state} endpoint="GET /api/v1/charts">
          {charts.state.status === "ready" && <TrendChart points={charts.state.data.temporal_trend} />}
        </EndpointState>
      </section>
    </div>
  );
}
