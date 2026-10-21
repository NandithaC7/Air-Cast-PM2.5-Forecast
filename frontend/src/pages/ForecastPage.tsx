import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getMetrics, getOverview, getSummary, postPrediction } from "../api/endpoints";
import { ConfusionMatrix } from "../components/ConfusionMatrix";
import { FieldList } from "../components/FieldList";
import { ForecastControls } from "../components/ForecastControls";
import { EndpointState, StateMessage, stationIdle } from "../components/StateMessage";
import { ThresholdNote } from "../components/ThresholdNote";
import { PROJECT_THRESHOLD_UG_M3 } from "../config";
import { useAppData } from "../context/AppData";
import { addCalendarDay, formatConcentration, formatMetric, formatPercent, formatWhen, modelDisplayName } from "../format";
import { useRequest } from "../hooks/useRequest";
import type { PredictV1Response, RequestState } from "../types";

function toErrorState(error: unknown): RequestState<PredictV1Response> {
  if (error instanceof ApiError) {
    if (error.kind === "not_configured") return { status: "not_configured", message: error.message };
    if (error.kind === "not_connected") return { status: "not_connected", message: error.message };
    return { status: "error", message: error.message };
  }
  return { status: "error", message: "The request failed before a response could be read." };
}

function classText(forecast: PredictV1Response): string {
  if (!forecast.available) return "Model not available";
  if (forecast.hazard_class === "hazard") return "Hazard";
  if (forecast.hazard_class === "no_hazard") return "No hazard";
  return "Hazard class not reported";
}

function periodText(period: { start: string | null; end: string | null } | null | undefined): string {
  if (!period || (!period.start && !period.end)) return "Not reported";
  return `${formatWhen(period.start)} to ${formatWhen(period.end)}`;
}

export function ForecastPage() {
  const { selectedStationId, refreshKey, stations } = useAppData();
  const enabled = selectedStationId != null;
  const metrics = useRequest(() => getMetrics(selectedStationId as number), [selectedStationId, refreshKey], enabled);
  const summary = useRequest(
    () => getSummary({ station_id: selectedStationId as number }),
    [selectedStationId, refreshKey],
    enabled,
  );
  const overview = useRequest(() => getOverview(), [refreshKey]);
  const [modelName, setModelName] = useState("logistic_regression");
  const [targetDate, setTargetDate] = useState("");
  const [forecast, setForecast] = useState<RequestState<PredictV1Response>>({ status: "idle" });
  const [validation, setValidation] = useState<string | null>(null);
  const minTarget =
    summary.state.status === "ready" && summary.state.data.first_feature_date
      ? addCalendarDay(summary.state.data.first_feature_date)
      : null;
  const maxTarget =
    summary.state.status === "ready"
      ? addCalendarDay(summary.state.data.latest_feature_date ?? summary.state.data.latest_daily_mean?.date ?? "")
      : null;

  useEffect(() => {
    document.title = "Forecast & Model · AirCast India";
  }, []);

  useEffect(() => {
    setForecast({ status: "idle" });
    setValidation(null);
    setTargetDate(maxTarget ?? "");
  }, [selectedStationId, maxTarget]);

  useEffect(() => {
    if (overview.state.status === "ready" && overview.state.data.preferred_model) {
      setModelName(overview.state.data.preferred_model);
    }
  }, [overview.state]);

  const forecastData = forecast.status === "ready" ? forecast.data : null;
  const metricsData = metrics.state.status === "ready" ? metrics.state.data : null;
  const reportedThreshold = forecastData?.threshold_ug_m3 ?? metricsData?.threshold_ug_m3 ?? null;

  const checkProbability = () => {
    setValidation(null);
    if (selectedStationId == null) {
      setValidation("Select a monitoring station before requesting a forecast.");
      return;
    }
    if (!targetDate) {
      setValidation("Choose a forecast target date.");
      return;
    }
    if (!minTarget || !maxTarget) {
      setValidation("This station has no labelled feature rows, so a next-day class cannot be requested.");
      return;
    }
    if (targetDate < minTarget || targetDate > maxTarget) {
      setValidation(`Choose a date between ${minTarget} and ${maxTarget}.`);
      return;
    }
    setForecast({ status: "loading" });
    postPrediction({ model_name: modelName, station_id: selectedStationId, target_date: targetDate }).then(
      (data) => {
        if (data.available && data.target_date && data.target_date !== targetDate) {
          setValidation(`The API scored ${data.target_date}, not ${targetDate}.`);
        }
        setForecast({ status: "ready", data });
      },
      (error: unknown) => setForecast(toErrorState(error)),
    );
  };

  return (
    <div>
      <header className="page-head">
        <h1>Forecast &amp; Model</h1>
        <p className="lede">
          Request a next-day hazard class from one of the four saved PySpark models. Historical concentrations are
          measured inputs. A probability is shown only when that model actually emits one.
        </p>
      </header>

      <section className="tile">
        <div className="tile-head">
          <h2>Check next-day probability</h2>
        </div>
        <p className="tile-detail">
          Logistic Regression, Decision Tree, and Random Forest can return a class probability. Linear SVM returns a
          decision score instead. The form calls POST /api/v1/predict and does not invent a successful result if the API
          fails.
        </p>
        <label className="field">
          <span>Model</span>
          <select value={modelName} onChange={(event) => setModelName(event.target.value)}>
            <option value="logistic_regression">Logistic Regression</option>
            <option value="decision_tree">Decision Tree</option>
            <option value="random_forest">Random Forest</option>
            <option value="linear_svm">Linear SVM</option>
          </select>
        </label>
        <ForecastControls
          targetDate={targetDate}
          minDate={minTarget}
          maxDate={maxTarget}
          onTargetDate={setTargetDate}
          onSubmit={checkProbability}
          busy={forecast.status === "loading"}
        />
        {validation && (
          <StateMessage tone="warning" title="Forecast date">
            {validation}
          </StateMessage>
        )}
      </section>

      <div className="split" style={{ marginTop: 14 }}>
        <section className="tile">
          <div className="section-head">
            <h2>Measured inputs</h2>
            <p>Values observed before the forecast. These are not predictions.</p>
          </div>
          <EndpointState
            state={forecast}
            endpoint="POST /api/v1/predict"
            idle={
              selectedStationId == null ? (
                stationIdle(stations, "GET /api/forecast")
              ) : (
                <StateMessage title="Not requested">
                  Use Check next-day probability. No measured or predicted values are filled until POST /api/v1/predict
                  returns.
                </StateMessage>
              )
            }
          >
            {forecastData && (
              <FieldList
                items={[
                  { label: "Latest input date", value: formatWhen(forecastData.input_date) },
                  { label: "Latest input timestamp", value: formatWhen(forecastData.input_data_timestamp) },
                  {
                    label: "Input daily mean PM2.5",
                    value: formatConcentration(forecastData.pm25_input_daily_mean, forecastData.unit),
                  },
                ]}
              />
            )}
          </EndpointState>
        </section>

        <section className={`tile ${forecastData?.hazard_class === "hazard" ? "tile-warn" : "tile-sage"}`}>
          <div className="section-head">
            <h2>Predicted hazard</h2>
            <p>Class and probability for the forecast target date.</p>
          </div>
          <EndpointState
            state={forecast}
            endpoint="POST /api/v1/predict"
            idle={
              selectedStationId == null ? (
                stationIdle(stations, "GET /api/forecast")
              ) : (
                <StateMessage title="Not requested">
                  Use Check next-day probability. No measured or predicted values are filled until POST /api/v1/predict
                  returns.
                </StateMessage>
              )
            }
          >
            {forecastData && (
              <>
                {!forecastData.available && (
                  <StateMessage title="Model not available">
                    {forecastData.reason ?? "The forecast endpoint reported that no model result is available."}
                  </StateMessage>
                )}
                <p className="metric-value">
                  {forecastData.available && forecastData.probability_supported && forecastData.probability != null
                    ? formatPercent(forecastData.probability)
                    : forecastData.available
                      ? classText(forecastData)
                      : "—"}
                </p>
                {forecastData.available && forecastData.interpretation && (
                  <p className="note">{forecastData.interpretation}</p>
                )}
                <FieldList
                  items={[
                    { label: "Forecast target date", value: formatWhen(forecastData.target_date) },
                    { label: "Predicted hazard class", value: classText(forecastData) },
                    {
                      label: forecastData.probability_supported ? "Probability" : "Decision score",
                      value: forecastData.probability_supported
                        ? formatPercent(forecastData.probability)
                        : forecastData.decision_score == null
                          ? "Not reported"
                          : formatMetric(forecastData.decision_score),
                    },
                    {
                      label: "Probability cutoff",
                      value:
                        forecastData.decision_threshold == null ? "Not reported" : formatMetric(forecastData.decision_threshold),
                    },
                    {
                      label: "Model",
                      value: forecastData.available
                        ? modelDisplayName(forecastData.model?.name) +
                          (forecastData.model?.version ? ` · ${forecastData.model.version}` : "")
                        : "Model not available",
                    },
                    { label: "Training-data period", value: periodText(forecastData.model?.training_period) },
                  ]}
                />
              </>
            )}
          </EndpointState>
        </section>
      </div>

      <section className="panel">
        <div className="section-head">
          <h2>Hazard threshold</h2>
        </div>
        <ThresholdNote reported={reportedThreshold} />
        <p className="note">
          A positive prediction means the model expects the next calendar day&apos;s mean PM2.5 at the selected station
          to exceed {PROJECT_THRESHOLD_UG_M3} µg/m³. That is an advisory flag, not a measured concentration.
        </p>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Evaluation</h2>
          <p>Precision, recall, F1, PR-AUC, and the confusion matrix appear when the metrics endpoint returns them.</p>
        </div>
        <EndpointState state={metrics.state} endpoint="GET /api/model/metrics" idle={stationIdle(stations, "GET /api/model/metrics")}>
          {metricsData && !metricsData.available && (
            <StateMessage title="Evaluation pending">
              {metricsData.reason ?? "The metrics endpoint reported that evaluation results are not available."}
            </StateMessage>
          )}
          {metricsData && metricsData.available && !metricsData.test && (
            <StateMessage title="Evaluation pending">The metrics payload did not include a test block.</StateMessage>
          )}
          {metricsData?.test && (
            <>
              <FieldList
                items={[
                  { label: "Model", value: modelDisplayName(metricsData.model?.name) },
                  { label: "Training-data period", value: periodText(metricsData.model?.training_period) },
                  { label: "Precision", value: formatMetric(metricsData.test.precision) },
                  { label: "Recall", value: formatMetric(metricsData.test.recall) },
                  { label: "F1-score", value: formatMetric(metricsData.test.f1) },
                  { label: "PR-AUC", value: formatMetric(metricsData.test.pr_auc) },
                  ...(metricsData.test.auc_roc == null
                    ? []
                    : [{ label: "ROC-AUC", value: formatMetric(metricsData.test.auc_roc) }]),
                  {
                    label: "Evaluation rows",
                    value: metricsData.test.n == null ? "—" : metricsData.test.n.toLocaleString("en-IN"),
                  },
                ]}
              />
              {metricsData.test.confusion ? (
                <ConfusionMatrix matrix={metricsData.test.confusion} />
              ) : (
                <p className="meta">The confusion matrix was not included in the test block.</p>
              )}
            </>
          )}
        </EndpointState>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Persistence baseline</h2>
          <p>
            The training stage can compare the model with a persistence rule: tomorrow repeats today&apos;s hazard
            label. Figures are filled only from the metrics payload.
          </p>
        </div>
        <EndpointState state={metrics.state} endpoint="GET /api/model/metrics" idle={stationIdle(stations, "GET /api/model/metrics")}>
          {metricsData && !metricsData.baseline && (
            <StateMessage title="Evaluation pending">Baseline results were not included in this response.</StateMessage>
          )}
          {metricsData?.baseline && metricsData.test && (
            <>
              {metricsData.baseline.description && <p className="note">{metricsData.baseline.description}</p>}
              <div className="table-wrap">
                <table>
                  <caption>Model scores beside the persistence baseline</caption>
                  <thead>
                    <tr>
                      <th scope="col">Metric</th>
                      <th scope="col">Model</th>
                      <th scope="col">Persistence baseline</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row">Precision</th>
                      <td className="num">{formatMetric(metricsData.test.precision)}</td>
                      <td className="num">{formatMetric(metricsData.baseline.precision)}</td>
                    </tr>
                    <tr>
                      <th scope="row">Recall</th>
                      <td className="num">{formatMetric(metricsData.test.recall)}</td>
                      <td className="num">{formatMetric(metricsData.baseline.recall)}</td>
                    </tr>
                    <tr>
                      <th scope="row">F1-score</th>
                      <td className="num">{formatMetric(metricsData.test.f1)}</td>
                      <td className="num">{formatMetric(metricsData.baseline.f1)}</td>
                    </tr>
                    <tr>
                      <th scope="row">PR-AUC</th>
                      <td className="num">{formatMetric(metricsData.test.pr_auc)}</td>
                      <td className="num">{formatMetric(metricsData.baseline.pr_auc)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {metricsData.baseline.confusion && (
                <>
                  <h3 className="subhead">Baseline confusion matrix</h3>
                  <ConfusionMatrix matrix={metricsData.baseline.confusion} />
                </>
              )}
            </>
          )}
        </EndpointState>
      </section>
    </div>
  );
}
